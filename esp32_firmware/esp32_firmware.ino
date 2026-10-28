/*
 * ==============================================================================
 * BAI GIU XE THONG MINH - ESP32-S3 N16R8 - 1 DAU DOC RC522
 * Phan loai THE CU DAN / THE KHACH
 * ==============================================================================
 * PHAN LOAI THE:
 *  - Cu dan : UID nam trong mang RESIDENT_UIDS[] (sua o khoi cau hinh).
 *  - Khach  : UID nam trong mang GUEST_UIDS[].
 *  - The la : khong nam trong 2 mang -> tu choi (neu REJECT_UNKNOWN_CARDS = 1),
 *             hoac coi nhu the khach (neu = 0).
 *
 * VAO (giong nhau cho ca 2 loai):
 *  IR NGOAI co xe + quet the + bai chua day -> luu the (kem gio vao) -> mo barie VAO.
 *  IR NGOAI het xe lien tuc 0.5s -> dong barie.
 *
 * RA:
 *  CU DAN : quet the + IR TRONG co xe -> MO NGAY, KHONG tinh tien, khong can nut.
 *           (Cu dan khong can lich su vao: mat dien/reset van ra duoc.)
 *  KHACH  : quet the + IR TRONG co xe -> tinh tien, hien len LCD, CHO bam NUT
 *           (15 giay). Bam nut -> mo barie, xoa khoi bai. Het gio -> huy.
 *           Khach khong co lich su vao (vd sau reset) -> tu choi.
 *
 * BARIE: tu dong dong khi IR het xe 0.5s, nhung LUON giu mo toi thieu
 *   GATE_MIN_OPEN_MS (3s) de kip co xe vao vung cam bien.
 *
 * TINH TIEN (khach): lam tron LEN theo khoi, toi thieu 1 khoi.
 *    phi = ceil(thoi_gian / BLOCK_SECONDS) * FEE_PER_BLOCK
 *  De thu nhanh: dat BLOCK_SECONDS = 30 (moi 30 giay tinh 1 khoi).
 *
 * DAU NOI:
 *  RC522 : SCK=39  MOSI=40  MISO=41  SS=42  RST=47   (bus FSPI)
 *  LCD   : SCK=1   MOSI=2   CS=15    DC=16  RST=17  LED=18  (bus HSPI)
 *  PCA9685 I2C: SDA=4  SCL=5  Addr 0x40   Kenh 0 = CA 2 barie (dang cung 1 kenh)
 *  IR NGOAI = GPIO 6   IR TRONG = GPIO 7   (LOW = co xe)
 *  NUT BAM  = GPIO 14 <-> GND     BUZZER = GPIO 8
 *
 * DIEU KHIEN TU APP (Python) QUA UART 115200:
 *  - CMD:GATE_OPEN / CMD:BARRIER_OPEN : mo barie (tu chon cong theo IR), giu 8s
 *  - CMD:GATE_IN_OPEN / CMD:GATE_OUT_OPEN : mo barie VAO / RA
 *  - CMD:GATE_CLOSE / CMD:BARRIER_CLOSE : dong ca 2
 *  - CMD:GATE_IN_CLOSE / CMD:GATE_OUT_CLOSE
 *  - CMD:BEEP_OK / CMD:BEEP_ERROR / CMD:BEEP_TEST : chuong
 *  - CMD:PING (tra PONG) / CMD:STATUS (trang thai 2 barie)
 *  - LCD:TEXT:<dong1>|<dong2>
 *  Moi lenh hop le deu duoc tra loi bang dong "ACK:..." de de kiem tra.
 *
 * NUT BAM (GPIO 14):
 *  - Khi KHACH dang cho xac nhan o cong RA -> thanh toan & mo barie RA.
 *  - Con lai -> nut thu cong: nhan 1 lan MO barie (giu 8s), nhan lan nua DONG.
 *
 * Thu vien: MFRC522v2 (OSSLibraries), Adafruit GFX, Adafruit ILI9341,
 *           Adafruit PWM Servo Driver
 * ==============================================================================
 */

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <MFRC522v2.h>
#include <MFRC522DriverSPI.h>
#include <MFRC522DriverPinSimple.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <Adafruit_PWMServoDriver.h>
#include <esp_system.h>

// ==============================================================================
// 1. CAU HINH
// ==============================================================================

// ---- DANH SACH THE ----
// UID viet HOA, lien nhau, khong dau ':' (vd 67:21:20:49 -> "67212049").
// Cach lay UID moi: quet the, doc dong "CARD:xxxxxxxx" tren Serial Monitor.
const char *const RESIDENT_UIDS[] = {   // THE CU DAN
  "67212049",
  "E7625224",
};
const char *const GUEST_UIDS[] = {      // THE KHACH
  "45398BE0",
  "45640BE0",
  "251DB7E0",
};
const int NUM_RESIDENTS = sizeof(RESIDENT_UIDS) / sizeof(RESIDENT_UIDS[0]);
const int NUM_GUESTS    = sizeof(GUEST_UIDS) / sizeof(GUEST_UIDS[0]);

// 1 = the khong nam trong 2 danh sach tren bi TU CHOI (giong bai that)
// 0 = the la tu dong duoc coi la the khach
#define REJECT_UNKNOWN_CARDS  1

// ---- Bieu phi (khach) ----
#define FEE_PER_BLOCK         5000    // VND moi khoi
#define BLOCK_SECONDS         3600    // 1 khoi = 1 gio (de demo: dat 30)

// --- RC522 ---
#define RFID_SCK_PIN       12
#define RFID_MOSI_PIN      11
#define RFID_MISO_PIN      13
#define RFID_SS_PIN        10
#define RFID_RST_PIN       9

// --- LCD ILI9341 (HSPI phan cung) ---
#define TFT_SCK_PIN        1
#define TFT_MOSI_PIN       2
#define TFT_CS_PIN         15
#define TFT_DC_PIN         16
#define TFT_RST_PIN        17
#define TFT_LED_PIN        18

// --- PCA9685 ---
#define I2C_SDA_PIN        4
#define I2C_SCL_PIN        5
#define PCA9685_ADDR       0x40
#define SERVO_ENTRY_CH     0
// HIEN TAI 2 servo CUNG cam vao kenh 0 cua PCA9685 -> 2 barie luon chuyen dong cung luc.
// Muon barie vao/ra DOC LAP: cam servo ra sang kenh 1 roi doi dong duoi thanh 1.
#define SERVO_EXIT_CH      0

// --- IR, nut, buzzer ---
#define IR_OUTSIDE_PIN     6
#define IR_INSIDE_PIN      7
#define BUTTON_PIN         14
#define BUZZER_PIN         8

// Chuong: 1 = chuong ACTIVE (cap dien la keu), 0 = chuong PASSIVE (can xung PWM)
#define BUZZER_ACTIVE         1
#define BUZZER_PASSIVE_FREQ   2700


// --- Thong so ---
// ---- Servo barie: xung (microsecond) DA DO bang servo_calibrate.ino ----
// DONG = thanh nam ngang, MO = thanh dung len.
// Neu thuc te bi nguoc (barie "mo" ma thanh nam ngang) thi DOI cho 2 so DONG/MO.
#define SERVO_ENTRY_CLOSED_US    2083
#define SERVO_ENTRY_OPEN_US      1238
#define SERVO_EXIT_CLOSED_US     2083
#define SERVO_EXIT_OPEN_US       1283

#define GATE_CLOSE_DELAY_MS   500     // IR het xe lien tuc bay nhieu ms -> dong barie
#define GATE_MIN_OPEN_MS      3000    // Barie giu mo TOI THIEU (khong tu dong dong som hon)
#define SCAN_DEBOUNCE_MS      2500
#define EXIT_CONFIRM_MS       15000   // Thoi gian khach cho bam nut
#define MANUAL_OPEN_HOLD_MS   8000    // Bam nut / lenh APP: giu barie mo toi thieu 8s
#define BUTTON_DEBOUNCE_MS    40
#define MAX_SLOTS             10
#define RFID_SPI_HZ           4000000

#define LCD_LINE_CHARS        22
#define LCD_BG                0x1082
#define HDR_BG                0x0011

// ==============================================================================
// 2. DOI TUONG
// ==============================================================================
SPIClass spiRfid(FSPI);
MFRC522DriverPinSimple ssPin(RFID_SS_PIN);
MFRC522DriverSPI driver{ssPin, spiRfid, SPISettings(RFID_SPI_HZ, MSBFIRST, SPI_MODE0)};
MFRC522 rfid{driver};

SPIClass lcdSPI(HSPI);
Adafruit_ILI9341 tft = Adafruit_ILI9341(&lcdSPI, TFT_DC_PIN, TFT_CS_PIN, TFT_RST_PIN);

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(PCA9685_ADDR);

// ==============================================================================
// 3. TRANG THAI
// ==============================================================================
struct Slot {
  String uid;
  bool resident;
  unsigned long inMs;     // millis() luc vao
};

Slot insideList[MAX_SLOTS];
int insideCount = 0;       // mat khi mat dien / reset

bool entryOpen = false;
bool exitOpen = false;
unsigned long entryClearSince = 0;
unsigned long exitClearSince = 0;
unsigned long entryOpenedAt = 0;
unsigned long exitOpenedAt = 0;
unsigned long entryMinOpenMs = GATE_MIN_OPEN_MS;   // thoi gian giu mo toi thieu (mo tay = lau hon)
unsigned long exitMinOpenMs  = GATE_MIN_OPEN_MS;

unsigned long lastScanTime = 0;

// Cho khach bam nut o cong RA
bool exitPending = false;
String exitPendingUid = "";
unsigned long exitPendingDeadline = 0;
unsigned long exitPendingFee = 0;
unsigned long exitPendingSeconds = 0;

int lastIrOutsideState = HIGH;
int lastIrInsideState = HIGH;

// ==============================================================================
// 4. KHAI BAO HAM
// ==============================================================================
void beep(int ms);
void beepOK();
void beepError();
void beepUpdate();
void buzzerWrite(bool on);
uint16_t usToTick(int us);
void printResetReason();
void openEntry(unsigned long minOpenMs = GATE_MIN_OPEN_MS);
void closeEntry();
void openExit(unsigned long minOpenMs = GATE_MIN_OPEN_MS);
void closeExit();
void openGatesSmart(unsigned long minOpenMs);
void toggleManualGate();
void handleUartCommands();
void processUartCommand(const String &line);
String asciiOnly(const String &s);
void showIdle();
void updateLcdHeader();
void updateLcdCount();
void updateLcdStatus(String line1, String line2, uint16_t color, String line3 = "");
String padLine(String s);
String getCardUID(MFRC522 &reader);
void resetRC522();
void handleCard(const String &uid);
bool buttonPressed();
bool isResident(const String &uid);
bool isGuest(const String &uid);
int  findInside(const String &uid);
void removeInside(int idx);
unsigned long calcFee(unsigned long seconds);
String formatDuration(unsigned long seconds);
void residentExit(const String &uid, int idx);

// ==============================================================================
// 5. SETUP
// ==============================================================================
void setup() {
  Serial.begin(115200);
  delay(100);
  printResetReason();

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  pinMode(IR_OUTSIDE_PIN, INPUT);
  pinMode(IR_INSIDE_PIN, INPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // LCD
  pinMode(TFT_LED_PIN, OUTPUT);
  digitalWrite(TFT_LED_PIN, HIGH);
  lcdSPI.begin(TFT_SCK_PIN, -1, TFT_MOSI_PIN, -1);
  tft.begin(40000000);
  tft.setRotation(1);
  tft.fillScreen(ILI9341_BLACK);
  updateLcdHeader();
  updateLcdStatus("DANG KHOI DONG...", "Kiem tra phan cung", ILI9341_YELLOW);

  // Servo
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, 100000);
  pwm.begin();
  pwm.setPWMFreq(50);
  delay(10);
  closeEntry();
  closeExit();

  // RC522 (MFRC522v2 khong tu reset -> reset phan cung tai day)
  resetRC522();
  spiRfid.begin(RFID_SCK_PIN, RFID_MISO_PIN, RFID_MOSI_PIN, -1);
  bool ok = rfid.PCD_Init();

  Serial.println("STATUS:ESP32_SYSTEM_READY");
  Serial.print("INFO:RC522_VER:0x");
  Serial.println((byte)rfid.PCD_GetVersion(), HEX);
  Serial.print("INFO:RESIDENT_CARDS:");
  Serial.println(NUM_RESIDENTS);
  Serial.print("INFO:GUEST_CARDS:");
  Serial.println(NUM_GUESTS);
  Serial.println("INFO:UART_CMD_READY");

  if (ok) {
    beepOK();
    showIdle();
  } else {
    Serial.println("ERROR:RC522_NOT_FOUND");
    beepError();
    updateLcdStatus("RC522: LOI", "Kiem tra day SPI/RST", ILI9341_RED);
  }
  updateLcdCount();
}

// ==============================================================================
// 6. LOOP
// ==============================================================================
void loop() {
  unsigned long now = millis();

  // --- Chuong: cap nhat khong chan (non-blocking) ---
  beepUpdate();

  // --- Lenh tu APP (Python) qua UART ---
  handleUartCommands();

  // --- Doc the ---
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    if (now - lastScanTime > SCAN_DEBOUNCE_MS) {
      lastScanTime = now;
      handleCard(getCardUID(rfid));
    }
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
  }

  // --- IR: bao su kien ---
  int irOutside = digitalRead(IR_OUTSIDE_PIN);
  int irInside  = digitalRead(IR_INSIDE_PIN);

  if (irOutside != lastIrOutsideState) {
    lastIrOutsideState = irOutside;
    Serial.println(irOutside == LOW ? "IR_OUTSIDE:DETECTED" : "IR_OUTSIDE:CLEAR");
  }
  if (irInside != lastIrInsideState) {
    lastIrInsideState = irInside;
    Serial.println(irInside == LOW ? "IR_INSIDE:DETECTED" : "IR_INSIDE:CLEAR");
  }

  // --- Nut bam:
  //     + KHACH dang cho xac nhan o cong RA -> thanh toan & mo barie RA
  //     + Con lai -> MO/DONG barie bang tay (nut thu cong)
  if (buttonPressed()) {
    Serial.println("BUTTON:PRESSED");
    if (exitPending && irInside == LOW) {
      int idx = findInside(exitPendingUid);
      if (idx >= 0) removeInside(idx);
      Serial.print("EXIT_OK:");
      Serial.print(exitPendingUid);
      Serial.print(":FEE:");
      Serial.print(exitPendingFee);
      Serial.print(":SEC:");
      Serial.println(exitPendingSeconds);
      exitPending = false;
      updateLcdStatus("DA THANH TOAN", "Chuc thuong lo!", ILI9341_GREEN);
      updateLcdCount();
      openExit();
    } else if (exitPending) {
      beepError();
      updateLcdStatus("Khong co xe o cong ra", "Dua xe vao cam bien", ILI9341_RED);
    } else {
      toggleManualGate();     // nut thu cong: mo/dong barie
    }
  }

  // --- Het thoi gian cho ---
  if (exitPending && (long)(now - exitPendingDeadline) >= 0) {
    exitPending = false;
    Serial.println("EXIT_PENDING:TIMEOUT");
    beepError();
    updateLcdStatus("Het thoi gian cho", "Quet lai the de ra", ILI9341_ORANGE);
  }

  // --- Dong barie VAO khi IR NGOAI het xe ---
  if (entryOpen) {
    if (irOutside == LOW) {
      entryClearSince = 0;
    } else if (now - entryOpenedAt < entryMinOpenMs) {
      entryClearSince = 0;               // chua du thoi gian mo toi thieu
    } else if (entryClearSince == 0) {
      entryClearSince = now;
    } else if (now - entryClearSince >= GATE_CLOSE_DELAY_MS) {
      closeEntry();
      showIdle();
    }
  }

  // --- Dong barie RA khi IR TRONG het xe ---
  if (exitOpen) {
    if (irInside == LOW) {
      exitClearSince = 0;
    } else if (now - exitOpenedAt < exitMinOpenMs) {
      exitClearSince = 0;                // chua du thoi gian mo toi thieu
    } else if (exitClearSince == 0) {
      exitClearSince = now;
    } else if (now - exitClearSince >= GATE_CLOSE_DELAY_MS) {
      closeExit();
      showIdle();
    }
  }

  delay(10);
}

// ==============================================================================
// 7. XU LY THE
// ==============================================================================
void handleCard(const String &uid) {
  bool carOutside = (digitalRead(IR_OUTSIDE_PIN) == LOW);
  bool carInside  = (digitalRead(IR_INSIDE_PIN) == LOW);
  bool resident   = isResident(uid);
  bool guest      = isGuest(uid);
  int idx = findInside(uid);

  Serial.print("CARD:");
  Serial.println(uid);
  Serial.println(resident ? "INFO:TYPE:RESIDENT" : (guest ? "INFO:TYPE:GUEST" : "INFO:TYPE:UNKNOWN"));
  Serial.print("INFO:IR_OUTSIDE:");
  Serial.print(carOutside ? "CO_XE" : "TRONG");
  Serial.print("  IR_INSIDE:");
  Serial.println(carInside ? "CO_XE" : "TRONG");

#if REJECT_UNKNOWN_CARDS
  if (!resident && !guest) {
    beepError();
    updateLcdStatus("THE KHONG HOP LE", "Lien he nhan vien", ILI9341_RED, "The: " + uid);
    Serial.println("DENY:UNKNOWN_CARD");
    return;
  }
#endif

  if (idx < 0) {
    // ---- THE CHUA GHI NHAN TRONG BAI ----
    if (carOutside) {
      // HUONG VAO (cu dan va khach nhu nhau)
      if (insideCount >= MAX_SLOTS) {
        beepError();
        updateLcdStatus("BAI DAY", "Het cho trong", ILI9341_RED);
        Serial.println("DENY:LOT_FULL");
        return;
      }
      insideList[insideCount].uid = uid;
      insideList[insideCount].resident = resident;
      insideList[insideCount].inMs = millis();
      insideCount++;

      exitPending = false;   // quet the moi huy yeu cau cho cu
      Serial.print("ENTRY_OK:");
      Serial.println(uid);
      updateLcdStatus(resident ? "CU DAN VAO" : "KHACH VAO", "Moi xe vao...", ILI9341_GREEN, "The: " + uid);
      updateLcdCount();
      openEntry();
    } else if (carInside && resident) {
      // Cu dan khong co lich su vao (vd sau reset) -> van cho ra, mien phi
      residentExit(uid, -1);
    } else if (carInside) {
      beepError();
      updateLcdStatus("THE CHUA VAO BAI", "Lien he nhan vien", ILI9341_RED, "The: " + uid);
      Serial.println("DENY:GUEST_NO_ENTRY_RECORD");
    } else {
      beepError();
      updateLcdStatus("Khong co xe o cong", "Dua xe vao cam bien", ILI9341_RED, "The: " + uid);
      Serial.println("DENY:NO_VEHICLE");
    }
    return;
  }

  // ---- THE DANG O TRONG BAI -> HUONG RA ----
  if (!carInside) {
    beepError();
    if (carOutside) {
      updateLcdStatus("THE DA O TRONG BAI", "Khong the vao lai", ILI9341_RED, "The: " + uid);
      Serial.println("DENY:ALREADY_INSIDE");
    } else {
      updateLcdStatus("Khong co xe o cong ra", "Dua xe vao cam bien", ILI9341_RED, "The: " + uid);
      Serial.println("DENY:NO_VEHICLE_INSIDE");
    }
    return;
  }

  if (insideList[idx].resident) {
    residentExit(uid, idx);          // cu dan: mo ngay, mien phi
    return;
  }

  // KHACH: tinh tien roi cho bam nut
  unsigned long seconds = (millis() - insideList[idx].inMs) / 1000UL;
  unsigned long fee = calcFee(seconds);

  exitPending = true;
  exitPendingUid = uid;
  exitPendingDeadline = millis() + EXIT_CONFIRM_MS;
  exitPendingFee = fee;
  exitPendingSeconds = seconds;

  Serial.print("EXIT_PENDING:");
  Serial.print(uid);
  Serial.print(":FEE:");
  Serial.print(fee);
  Serial.print(":SEC:");
  Serial.println(seconds);

  char buf[28];
  snprintf(buf, sizeof(buf), "PHI: %lu VND", fee);
  beep(80);
  updateLcdStatus(String(buf), "Do: " + formatDuration(seconds), ILI9341_YELLOW,
                  "Nhan nut de ra");
}

// Cu dan ra: khong tinh tien, mo barie ngay. idx < 0 neu khong co ban ghi vao.
void residentExit(const String &uid, int idx) {
  if (idx >= 0) removeInside(idx);
  exitPending = false;
  Serial.print("EXIT_FREE:");
  Serial.println(uid);
  updateLcdStatus("CU DAN RA", "Mien phi - Moi xe ra", ILI9341_GREEN, "The: " + uid);
  updateLcdCount();
  openExit();
}

// ==============================================================================
// 8. PHAN LOAI THE, DANH SACH, PHI
// ==============================================================================
bool isResident(const String &uid) {
  for (int i = 0; i < NUM_RESIDENTS; i++) {
    if (uid == RESIDENT_UIDS[i]) return true;
  }
  return false;
}

bool isGuest(const String &uid) {
  for (int i = 0; i < NUM_GUESTS; i++) {
    if (uid == GUEST_UIDS[i]) return true;
  }
  return false;
}

int findInside(const String &uid) {
  for (int i = 0; i < insideCount; i++) {
    if (insideList[i].uid == uid) return i;
  }
  return -1;
}

void removeInside(int idx) {
  insideList[idx] = insideList[insideCount - 1];
  insideList[insideCount - 1].uid = "";
  insideCount--;
}

// Lam tron len theo khoi, toi thieu 1 khoi
unsigned long calcFee(unsigned long seconds) {
  unsigned long blocks = (seconds + BLOCK_SECONDS - 1) / BLOCK_SECONDS;
  if (blocks < 1) blocks = 1;
  return blocks * (unsigned long)FEE_PER_BLOCK;
}

String formatDuration(unsigned long seconds) {
  unsigned long h = seconds / 3600;
  unsigned long m = (seconds % 3600) / 60;
  unsigned long s = seconds % 60;
  char buf[32];
  if (h > 0) snprintf(buf, sizeof(buf), "%lu:%02lu:%02lu", h, m, s);
  else       snprintf(buf, sizeof(buf), "%02lu:%02lu", m, s);
  return String(buf);
}

// ==============================================================================
// 9. NUT BAM (chong doi phim, tra ve true 1 lan khi vua nhan xuong)
// ==============================================================================
bool buttonPressed() {
  static int lastRaw = HIGH;
  static int stable = HIGH;
  static unsigned long lastChange = 0;

  int raw = digitalRead(BUTTON_PIN);
  if (raw != lastRaw) {
    lastRaw = raw;
    lastChange = millis();
  }
  if (millis() - lastChange > BUTTON_DEBOUNCE_MS && raw != stable) {
    stable = raw;
    if (stable == LOW) return true;
  }
  return false;
}

// ==============================================================================
// 10. BARIE
// ==============================================================================
// Doi xung (us) -> tick cua PCA9685 (50Hz, 4096 tick / 20ms ~ 4.88us/tick)
uint16_t usToTick(int us) {
  if (us < 400) us = 400;
  if (us > 2600) us = 2600;       // chan an toan, khong cho xung qua khoang
  return (uint16_t)(us * 0.2048f + 0.5f);
}

void openEntry(unsigned long minOpenMs) {
  pwm.setPWM(SERVO_ENTRY_CH, 0, usToTick(SERVO_ENTRY_OPEN_US));
  entryOpen = true;
  entryClearSince = 0;
  entryOpenedAt = millis();
  entryMinOpenMs = (minOpenMs > 0) ? minOpenMs : GATE_MIN_OPEN_MS;
  Serial.println("GATE_ENTRY:OPEN");
  beep(120);
}

void closeEntry() {
  pwm.setPWM(SERVO_ENTRY_CH, 0, usToTick(SERVO_ENTRY_CLOSED_US));
  Serial.println("GATE_ENTRY:CLOSE");
  entryOpen = false;
  entryClearSince = 0;
  entryMinOpenMs = GATE_MIN_OPEN_MS;
}

void openExit(unsigned long minOpenMs) {
  pwm.setPWM(SERVO_EXIT_CH, 0, usToTick(SERVO_EXIT_OPEN_US));
  exitOpen = true;
  exitClearSince = 0;
  exitOpenedAt = millis();
  exitMinOpenMs = (minOpenMs > 0) ? minOpenMs : GATE_MIN_OPEN_MS;
  Serial.println("GATE_EXIT:OPEN");
  beep(120);
}

void closeExit() {
  pwm.setPWM(SERVO_EXIT_CH, 0, usToTick(SERVO_EXIT_CLOSED_US));
  Serial.println("GATE_EXIT:CLOSE");
  exitOpen = false;
  exitClearSince = 0;
  exitMinOpenMs = GATE_MIN_OPEN_MS;
}

// Mo barie theo huong phat hien duoc o cam bien IR.
// Khong ro huong (hoac ca 2 cong deu co xe) -> mo ca 2.
void openGatesSmart(unsigned long minOpenMs) {
  bool carOutside = (digitalRead(IR_OUTSIDE_PIN) == LOW);
  bool carInside  = (digitalRead(IR_INSIDE_PIN) == LOW);

  if (carOutside && !carInside) {
    openEntry(minOpenMs);
  } else if (carInside && !carOutside) {
    openExit(minOpenMs);
  } else {
    openEntry(minOpenMs);
    openExit(minOpenMs);
  }
}

// Nut bam thu cong: dang mo -> dong, dang dong -> mo (giu mo MANUAL_OPEN_HOLD_MS)
void toggleManualGate() {
  if (entryOpen || exitOpen) {
    closeEntry();
    closeExit();
    showIdle();
    Serial.println("MANUAL:GATE_CLOSE");
    return;
  }

  openGatesSmart(MANUAL_OPEN_HOLD_MS);
  updateLcdStatus("MO BARIE TAY", "Nhan nut de dong", ILI9341_GREEN);
  Serial.println("MANUAL:GATE_OPEN");
}

// ==============================================================================
// 11. BUZZER (chuong) - KHONG CHAN
// ==============================================================================
// Truoc day beep() dung delay() nen: bam nut/quet the luc chuong keu thi IR va
// barie bi dung lai, lenh APP gui toi cung bi tre. Gio chuong chay theo mau
// (keu bao nhieu ms, nghi bao nhieu ms, lap may lan) va duoc cap nhat trong loop.
static bool          buzzerIsOn   = false;
static uint8_t       buzzerSteps  = 0;
static uint16_t      buzzerOnMs   = 0;
static uint16_t      buzzerOffMs  = 0;
static unsigned long buzzerNextAt = 0;

void buzzerWrite(bool on) {
  buzzerIsOn = on;
#if BUZZER_ACTIVE
  digitalWrite(BUZZER_PIN, on ? HIGH : LOW);
#else
  if (on) tone(BUZZER_PIN, BUZZER_PASSIVE_FREQ);
  else    noTone(BUZZER_PIN);
#endif
}

// Bat dau mau tieng: keu onMs, nghi offMs, lap lai steps lan.
void beepPattern(uint16_t onMs, uint16_t offMs, uint8_t steps) {
  buzzerOnMs   = onMs;
  buzzerOffMs  = offMs;
  buzzerSteps  = steps;
  buzzerNextAt = millis();
  buzzerWrite(false);
}

void beep(int ms)  { beepPattern((uint16_t)ms, 0, 1); }
void beepOK()      { beepPattern(100, 60, 2); }
void beepError()   { beepPattern(120, 80, 3); }

void beepUpdate() {
  if (buzzerSteps == 0) {
    if (buzzerIsOn) buzzerWrite(false);
    return;
  }

  unsigned long now = millis();
  if ((long)(now - buzzerNextAt) < 0) return;

  if (buzzerIsOn) {
    buzzerWrite(false);
    buzzerSteps--;
    buzzerNextAt = now + buzzerOffMs;
  } else if (buzzerSteps > 0) {
    buzzerWrite(true);
    buzzerNextAt = now + buzzerOnMs;
  }
}

// ==============================================================================
// 11b. LENH TU APP (Python) GUI QUA UART
// ==============================================================================
// App gui dang text + '\n'. Cac lenh duoc ho tro:
//   CMD:GATE_OPEN / CMD:BARRIER_OPEN   -> mo barie (tu chon cong theo IR)
//   CMD:GATE_IN_OPEN                   -> mo barie VAO
//   CMD:GATE_OUT_OPEN                  -> mo barie RA
//   CMD:GATE_CLOSE / CMD:BARRIER_CLOSE -> dong ca 2 barie
//   CMD:GATE_IN_CLOSE / CMD:GATE_OUT_CLOSE
//   CMD:BEEP_OK / CMD:BEEP_ERROR       -> chuong bao thanh cong / loi
//   CMD:BEEP_TEST                      -> keu thu 1 tieng
//   CMD:STATUS                         -> in trang thai 2 barie
//   LCD:TEXT:<dong1>|<dong2>           -> hien thi len LCD
void handleUartCommands() {
  static String rxLine = "";

  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\n' || c == '\r') {
      rxLine.trim();
      if (rxLine.length() > 0) processUartCommand(rxLine);
      rxLine = "";
    } else if (rxLine.length() < 120) {
      rxLine += c;
    }
  }
}

// Bo dau tieng Viet (LCD chi co font ASCII) de khong hien ky tu rac.
String asciiOnly(const String &s) {
  String out = "";
  for (size_t i = 0; i < s.length(); i++) {
    if ((uint8_t)s[i] < 0x80) out += s[i];
  }
  return out;
}

void processUartCommand(const String &raw) {
  // LCD can giu nguyen chu hoa/thuong cua noi dung -> xu ly truoc khi upper().
  if (raw.startsWith("LCD:TEXT:")) {
    String payload = asciiOnly(raw.substring(9));
    int sep = payload.indexOf('|');
    String line1 = (sep >= 0) ? payload.substring(0, sep) : payload;
    String line2 = (sep >= 0) ? payload.substring(sep + 1) : "";
    updateLcdStatus(line1, line2, ILI9341_YELLOW);
    Serial.println("ACK:LCD");
    return;
  }

  String cmd = raw;
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "CMD:GATE_OPEN" || cmd == "CMD:BARRIER_OPEN") {
    openGatesSmart(MANUAL_OPEN_HOLD_MS);
    updateLcdStatus("MO BARIE (APP)", "Moi xe di chuyen...", ILI9341_GREEN);
    Serial.println("ACK:GATE_OPEN");
  } else if (cmd == "CMD:GATE_IN_OPEN") {
    openEntry(MANUAL_OPEN_HOLD_MS);
    updateLcdStatus("MO BARIE VAO", "Moi xe vao...", ILI9341_GREEN);
    Serial.println("ACK:GATE_IN_OPEN");
  } else if (cmd == "CMD:GATE_OUT_OPEN") {
    openExit(MANUAL_OPEN_HOLD_MS);
    updateLcdStatus("MO BARIE RA", "Moi xe ra...", ILI9341_GREEN);
    Serial.println("ACK:GATE_OUT_OPEN");
  } else if (cmd == "CMD:GATE_CLOSE" || cmd == "CMD:BARRIER_CLOSE") {
    closeEntry();
    closeExit();
    showIdle();
    Serial.println("ACK:GATE_CLOSE");
  } else if (cmd == "CMD:GATE_IN_CLOSE") {
    closeEntry();
    Serial.println("ACK:GATE_IN_CLOSE");
  } else if (cmd == "CMD:GATE_OUT_CLOSE") {
    closeExit();
    Serial.println("ACK:GATE_OUT_CLOSE");
  } else if (cmd == "CMD:BEEP_OK") {
    beepOK();
    Serial.println("ACK:BEEP_OK");
  } else if (cmd == "CMD:BEEP_ERROR") {
    beepError();
    updateLcdStatus("CANH BAO!", "The khong hop le / Loi", ILI9341_RED);
    Serial.println("ACK:BEEP_ERROR");
  } else if (cmd == "CMD:BEEP_TEST") {
    beep(300);
    Serial.println("ACK:BEEP_TEST");
  } else if (cmd == "CMD:PING") {
    Serial.println("PONG");
  } else if (cmd == "CMD:STATUS") {
    Serial.print("STATUS:ENTRY:");
    Serial.print(entryOpen ? "OPEN" : "CLOSE");
    Serial.print(":EXIT:");
    Serial.println(exitOpen ? "OPEN" : "CLOSE");
  } else {
    Serial.print("ERR:UNKNOWN_CMD:");
    Serial.println(raw);
  }
}

// In ly do reset. BROWNOUT = nguon sut ap (thuong do servo hut dong lon)
void printResetReason() {
  esp_reset_reason_t r = esp_reset_reason();
  Serial.print("INFO:RESET_REASON:");
  Serial.print((int)r);
  switch (r) {
    case ESP_RST_POWERON:  Serial.println(" (POWERON - cam nguon/nhan EN)"); break;
    case ESP_RST_SW:       Serial.println(" (SW)"); break;
    case ESP_RST_PANIC:    Serial.println(" (PANIC - loi chuong trinh)"); break;
    case ESP_RST_BROWNOUT: Serial.println(" (BROWNOUT - NGUON SUT AP)"); break;
    default:               Serial.println(""); break;
  }
}

// ==============================================================================
// 12. RFID
// ==============================================================================
void resetRC522() {
  pinMode(RFID_RST_PIN, OUTPUT);
  digitalWrite(RFID_RST_PIN, LOW);
  delay(10);
  digitalWrite(RFID_RST_PIN, HIGH);
  delay(50);
}

String getCardUID(MFRC522 &reader) {
  String uidStr = "";
  for (byte i = 0; i < reader.uid.size; i++) {
    if (reader.uid.uidByte[i] < 0x10) uidStr += "0";
    uidStr += String(reader.uid.uidByte[i], HEX);
  }
  uidStr.toUpperCase();
  return uidStr;
}

// ==============================================================================
// 13. LCD
// ==============================================================================
String padLine(String s) {
  if (s.length() > LCD_LINE_CHARS) s = s.substring(0, LCD_LINE_CHARS);
  while (s.length() < LCD_LINE_CHARS) s += ' ';
  return s;
}

void updateLcdHeader() {
  tft.fillRect(0, 0, 320, 45, HDR_BG);
  tft.drawFastHLine(0, 45, 320, ILI9341_CYAN);

  tft.setTextColor(ILI9341_WHITE);
  tft.setTextSize(2);
  tft.setCursor(15, 12);
  tft.print("BAI XE THONG MINH");

  tft.fillRect(10, 60, 300, 130, LCD_BG);
  tft.drawFastHLine(0, 210, 320, 0x3186);
}

// So xe dang trong bai / suc chua (goc phai header)
void updateLcdCount() {
  char buf[16];
  snprintf(buf, sizeof(buf), "XE: %d/%d ", insideCount, MAX_SLOTS);
  tft.setTextSize(1);
  tft.setTextColor(ILI9341_GREEN, HDR_BG);
  tft.setCursor(250, 16);
  tft.print(buf);
}

void showIdle() {
  updateLcdStatus("SAN SANG", "Quet the khi co xe", ILI9341_GREEN);
}

void updateLcdStatus(String line1, String line2, uint16_t color, String line3) {
  tft.drawRect(10, 60, 300, 130, color);

  tft.setTextSize(2);
  tft.setTextColor(color, LCD_BG);
  tft.setCursor(20, 75);
  tft.print(padLine(line1));

  tft.setTextColor(ILI9341_WHITE, LCD_BG);
  tft.setCursor(20, 110);
  tft.print(padLine(line2));

  tft.setTextColor(ILI9341_LIGHTGREY, LCD_BG);
  tft.setCursor(20, 145);
  tft.print(padLine(line3));

  tft.setTextSize(1);
  tft.setTextColor(ILI9341_LIGHTGREY, ILI9341_BLACK);
  tft.setCursor(15, 220);
  tft.print("NGOAI: ");
  tft.print((digitalRead(IR_OUTSIDE_PIN) == LOW) ? "CO XE  " : "TRONG  ");

  tft.setCursor(170, 220);
  tft.print("TRONG: ");
  tft.print((digitalRead(IR_INSIDE_PIN) == LOW) ? "CO XE  " : "TRONG  ");
}

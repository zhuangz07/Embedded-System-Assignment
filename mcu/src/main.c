
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "hw_memmap.h"
#include "debug.h"
#include "gpio.h"
#include "hw_i2c.h"
#include "hw_types.h"
#include "i2c.h"
#include "pin_map.h"
#include "sysctl.h"
#include "systick.h"
#include "interrupt.h"
#include "uart.h"
#include "hw_ints.h"
#include "pwm.h"

#define SYSTICK_FREQUENCY					1000			// 1000Hz

#define	I2C_FLASHTIME						500				// 500ms
#define GPIO_FLASHTIME						300				// 300ms


//*****************************************************************************
//I2C GPIO chip address and resigster define
//*****************************************************************************
#define TCA6424_I2CADDR 					0x22
#define PCA9557_I2CADDR						0x18

#define PCA9557_INPUT						0x00
#define	PCA9557_OUTPUT						0x01
#define PCA9557_POLINVERT					0x02
#define PCA9557_CONFIG						0x03

#define TCA6424_CONFIG_PORT0				0x0c
#define TCA6424_CONFIG_PORT1				0x0d
#define TCA6424_CONFIG_PORT2				0x0e

#define TCA6424_INPUT_PORT0					0x00
#define TCA6424_INPUT_PORT1					0x01
#define TCA6424_INPUT_PORT2					0x02

#define TCA6424_OUTPUT_PORT0				0x04
#define TCA6424_OUTPUT_PORT1				0x05
#define TCA6424_OUTPUT_PORT2				0x06


#define DISP_LEN 				8				// 8位数码管
#define MY_STUDENT_ID 			"31910229"
#define MY_CLASS_ID				"AU2421  "
#define MY_NAME					"GAOJX   "
#define FW_VERSION				"V1.0.0  "

/* =================== 串口通信协议相关定义 ====================== */
#define PROTO_MAX_FRAME_LEN     64
#define PROTO_ARG_MAX            6
#define PROTO_MSG_MAX_LEN       32

#define OK_STR					"OK"
#define ERROR_SYNTAX_STR		"ERROR SYNTAX"
#define ERROR_PARAM_STR			"ERROR PARAM"
#define ERROR_RANGE_STR			"ERROR RANGE"
#define ERROR_LEN_STR			"ERROR LEN"
#define ERROR_BUSY_STR			"ERROR BUSY"

/* ---------- 滚动方向 ---------- */
typedef enum {
    FORMAT_LEFT = 0,
    FORMAT_RIGHT
} FORMAT_DIR;
FORMAT_DIR display_format = FORMAT_LEFT;     // 默认左向

bool display_on = true;                       // 数码管亮灭
char user_msg[PROTO_MSG_MAX_LEN + 1] = {0};   // 用户自定义滚动消息
volatile uint8_t user_msg_active = 0;          // 是否有滚动消息

/* MSG文本的当前起始显示位置(用于滚动), 负数表示不滚动 */
volatile int16_t msg_scroll_offset = 0;
volatile uint32_t last_msg_scroll_tick = 0;
volatile uint8_t scroll_speed = 500;       // 滚动速度 (ms), 默认500ms

/* 远程蜂鸣时长 */
volatile uint32_t remote_beep_ms = 0;
volatile uint32_t remote_beep_start_tick = 0;	


/* =========================================================================== */
/*                    变量定义&函数声明                                         */
/* =========================================================================== */


/* =============== 系统时钟 & 软定时器 =================== */
uint32_t ui32SysClock;	//系统时钟频率

volatile uint32_t systick_count;
volatile uint8_t flag_1ms, flag_2ms, flag_10ms, flag_100ms, flag_1s;

void delay_ms(uint32_t value);
void Delay(uint32_t value)
{
	uint32_t ui32Loop;
	for(ui32Loop = 0; ui32Loop < value; ui32Loop++){};
}

// volatile uint8_t result,cnt,key_value,gpio_status;
// volatile uint8_t rightshift = 0x01;

/* =================== GPIO ====================== */
void S800_GPIO_Init(void);

/* =================== PWM ====================== */

#define BUZZER_FREQ 3000
uint32_t pwm_period = 0;
void S800_PWM_Init(void);

bool buzzer_state = false;
void Buzzer_On(void);
void Buzzer_Off(void);
void Buzzer_Toggle(void);

/* =================== UART ====================== */
#define UART_BUFFER_SIZE 128

char TxBuf[UART_BUFFER_SIZE];
volatile char RxBuf[UART_BUFFER_SIZE];
// volatile uint32_t RxBufIndex = 0;
volatile uint8_t RxEndFlag = 0;

void S800_UART_Init(void);
void UARTStringPut(const char *cMessage);
void UARTStringPutNonBlocking(const unsigned char *msg);

/* =================== 协议处理函数 ====================== */

// ---- 辅助工具 ----
#define toupper(c) (((c) >= 'a' && (c) <= 'z') ? ((c) - 0x20) : (c))

void str_toupper(char *s);
void str_reverse(char *dst, const char *src, int len);
void format_reverse(char *buf, const char *val);
void respond(const char *resp);
void respond_error(const char *err);
void respond_ok_data(const char *data);
void respond_ok(void);

// ---- 缩写匹配 ----
bool match_abbr(const char *input, const char *pattern);

// ---- 帧解析 ----
bool parse_frame(const char *raw, char *cmd, int cmd_size,
                 char args[PROTO_ARG_MAX][PROTO_MAX_FRAME_LEN/2], int *argc);

// ---- 命令处理 ----
void process_command(const char *raw);
void cmd_RST(void);
void cmd_SET(char args[PROTO_ARG_MAX][PROTO_MAX_FRAME_LEN/2], int argc);
void cmd_GET(char args[PROTO_ARG_MAX][PROTO_MAX_FRAME_LEN/2], int argc);
void cmd_PING(void);

// ---- 主动上报 ----
void evt_send_edit(const char *type, const char *value);
void evt_send_disp(void);
void evt_send_led(void);
void evt_send_key(const char *name);
void evt_send_alarm(void);
void evt_send_alarm_off(void);
void evt_send_mode(const char *state);


/* ===================== I2C ========================= */

void S800_I2C0_Init(void);
uint8_t I2C0_WriteByte(uint8_t DevAddr, uint8_t RegAddr, uint8_t WriteData);
uint32_t I2C0_ReadByte(uint8_t DevAddr, uint8_t RegAddr);

void led_on(uint8_t bitmap);

/* ==================== 数码管 ==================== */

const uint8_t seg7_digit[]  = {
    0x3f,   // 0
    0x06,   // 1
    0x5b,   // 2
    0x4f,   // 3
    0x66,   // 4
    0x6d,   // 5
    0x7d,   // 6
    0x07,   // 7
    0x7f,   // 8
    0x6f,   // 9
    0x77,   // A
    0x7c,   // B
    0x58,   // C
    0x5e,   // D
    0x79,   // E
    0x71    // F
};

const uint8_t seg7_letter[] = {
	0x77, // A
	0x7c, // B
	0x39, // C
	0x5e, // D
	0x79, // E
	0x71, // F
	0x3d, // G
	0x76, // H
	0x06, // I
	0x1e, // J
	0x75, // K
	0x3c, // L
	0x55, // M
	0x37, // N
	0x3f, // O
	0x73, // P
	0x67, // Q
	0x70, // R
	0x6d, // S
	0x78, // T
	0x3e, // U
	0x7e, // V
	0x6a, // W
	0x36, // X
	0x6e, // Y
		0x49  // Z
};

static char seg7_glyph_to_char(uint8_t glyph) {
	int i;
    // 先在数字表里找
    for (i = 0; i < 16; i++) {
        if (seg7_digit[i] == glyph)
            return (i < 10) ? ('0' + i) : ('A' + (i - 10));
    }
    // 再在字母表里找
    for (i = 0; i < 26; i++) {
        if (seg7_letter[i] == glyph)
            return 'A' + i;
    }
    return '_';
}

uint8_t seg_display_buffer[DISP_LEN] = {0};	// 数码管显示内容缓存
static uint8_t seg_display_pos = 0;

void seg_write(uint8_t pos, uint8_t value);
void seg_set_display(const char* str);
void seg_clear(void);
void seg_refresh(void);

void boot_display(void);

uint8_t scroll_str[64] = {0};
// typedef enum{
// 	SCROLL_IDLE = 0,
// 	SCROLL_LEFT, 
// 	SCROLL_RIGHT
// } SCROLL_DIR;

/* ================= 电子时钟 ================ */

typedef struct{
	uint16_t year;
	uint8_t month;
	uint8_t day;
} date_t;

typedef struct{
	uint8_t hour;
	uint8_t min;
	uint8_t sec;
} time_t;

date_t system_date = {2026, 6, 1};
time_t system_time = {12, 0, 0};

bool date_equal(date_t date1, date_t date2);
bool time_equal(time_t time1, time_t time2);

bool is_leap(uint16_t year);
bool is_valid_date(date_t date);
bool is_valid_time(time_t time);

void add_sys_sec(void);
void add_sys_min(void);
void add_sys_hour(void);
void add_sys_day(void);
void add_sys_month(void);
void add_sys_year(void);

bool add_sec(time_t *time);
bool add_min(time_t *time);
bool add_hour(time_t *time);

bool add_day(date_t *date);
bool add_month(date_t *date);
bool add_year(date_t *date);

void show_time(void);
void show_date_1(void);
void show_date_2(void);

time_t alarm_time = {19, 0, 5};
volatile uint8_t alarming = 0;

void alarm(void);

/* ======================= 按键处理 ======================= */
typedef enum{
	KEY_NONE = 0, 
	/* K1-K8 I2C */
	KEY_FUNC, 
	KEY_SHIFT, 
	KEY_ADD, 
	KEY_SAVE,
	KEY_DISP, 
	KEY_SPEED, 
	KEY_FORMAT, 
	KEY_EXT, 
	/* PJ0, PJ1 GPIO */
	KEY_USER1, 
	KEY_USER2
} KEY_ID;		// 按键定义

typedef enum{
	KEY_IDLE = 0,
	KEY_TAP,		// 短按
	KEY_PRESS,		// 长按
	KEY_PRESSUP
} KEY_STATE;	// 按键状态

uint8_t is_add_pressing = 0;

typedef enum{
	ON_BORAD = 0,
	OTHER,
} EVT_SRC;		//按键事件来源

typedef struct{
	KEY_ID key;
	KEY_STATE state;
	EVT_SRC source;
} KEY_EVENT;	// 按键事件

// -------- 按键事件队列 ----------

#define KEY_QUEUE_SIZE 16

KEY_EVENT key_queue[KEY_QUEUE_SIZE];
volatile uint8_t key_queue_head;
volatile uint8_t key_queue_tail;

bool key_queue_empty(void);
bool key_queue_full(void);
uint8_t key_push(KEY_EVENT ev);
KEY_EVENT *key_pop(void);

//------ 按键扫描 ------

#define KEY_SCAN_FREQ  100 //Hz
#define KEY_PRESS_TIME 800 //ms
#define KEY_DEBOUNCE_TIME 20 //ms

void key_scan(void);
void key_event_dispatch(void);

//------------ 按键回调函数 -----------------
typedef void (*KEY_Cb)(KEY_EVENT ev);

void KEY_FUNC_Cb(KEY_EVENT ev);
void KEY_SHIFT_Cb(KEY_EVENT ev);
void KEY_ADD_Cb(KEY_EVENT ev);
void KEY_SAVE_Cb(KEY_EVENT ev);
void KEY_DISP_Cb(KEY_EVENT ev);
void KEY_SPEED_Cb(KEY_EVENT ev);
void KEY_FORMAT_Cb(KEY_EVENT ev);
void KEY_EXT_Cb(KEY_EVENT ev);
void KEY_USER1_Cb(KEY_EVENT ev);
void KEY_USER2_Cb(KEY_EVENT ev);

const KEY_Cb key_cb[] = {
	KEY_FUNC_Cb, 
	KEY_SHIFT_Cb,
	KEY_ADD_Cb,
	KEY_SAVE_Cb,
	KEY_DISP_Cb,
	KEY_SPEED_Cb,
	KEY_FORMAT_Cb,
	KEY_EXT_Cb,
	KEY_USER1_Cb,
	KEY_USER2_Cb
};

/* ======================= 系统显示模式&设置项 ======================= */

typedef enum{
	MODE_BOOT = 0,
	MODE_SHOW_TIME,
	MODE_SHOW_DATE_1,
	MODE_SHOW_DATE_2,
	MODE_SETTING
} SYSTEM_MODE;		// 系统显示模式
SYSTEM_MODE system_mode = MODE_SHOW_TIME;
SYSTEM_MODE temp_mode = MODE_BOOT;		// 用于进入设置项后，保存进入前的模式

typedef enum{
	SET_DATE = 0,
	SET_TIME,
	SET_ALARM
} SET_ITEM;			// 设置项
SET_ITEM setting = SET_DATE;

typedef enum{
	SET_YEAR_HOUR = 0,
	SET_MONTH_MIN,
	SET_DAY_SEC
} SET_SUBITEM;		// 子设置项
SET_SUBITEM subitem = SET_YEAR_HOUR;

// 用于临时存储未保存的设置项
date_t temp_date;
time_t temp_time, temp_alarm;

// 设置超时计时器
volatile uint32_t setting_timeout_timer = 0;

void add_cur_subitem(void);

volatile uint32_t last_blink_tick = 0;
bool blinker = true;
void blink_cur_subitem(void);

void quit_setting(void);


/* ========================= UART function ================================== */

void S800_UART_Init(void)
{
	SysCtlPeripheralEnable(SYSCTL_PERIPH_UART0);
  	SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOA);						//Enable PortA
	while(!SysCtlPeripheralReady(SYSCTL_PERIPH_GPIOA));			//Wait for the GPIO moduleA ready

	GPIOPinConfigure(GPIO_PA0_U0RX);												// Set GPIO A0 and A1 as UART pins.
 	GPIOPinConfigure(GPIO_PA1_U0TX);    			

  	GPIOPinTypeUART(GPIO_PORTA_BASE, GPIO_PIN_0 | GPIO_PIN_1);

	// Configure the UART for 115,200, 8-N-1 operation.
  	UARTConfigSetExpClk(UART0_BASE, ui32SysClock,115200,
						(UART_CONFIG_WLEN_8 | UART_CONFIG_STOP_ONE | UART_CONFIG_PAR_NONE));
	UARTFIFOEnable(UART0_BASE);
	UARTFIFOLevelSet(UART0_BASE, UART_FIFO_TX4_8, UART_FIFO_RX4_8);
	// UARTStringPut((uint8_t *)"Hello, world!\r\n");
}

void UARTStringPut(const char *cMessage)
{
	while(*cMessage!='\0')
		UARTCharPut(UART0_BASE,*(cMessage++));
}

void UARTStringPutNonBlocking(const unsigned char *msg)
{
	while(*msg != '\0') {
		if (UARTSpaceAvail(UART0_BASE)) //发送FIFO有空位
			UARTCharPutNonBlocking(UART0_BASE, *msg++); //发送一个字符
	}
}

/* ========================= 协议工具函数 ================================== */

void str_toupper(char *s)
{
    while (*s) {
        *s = (char)toupper((unsigned char)*s);
        s++;
    }
}

void str_reverse(char *dst, const char *src, int len)
{
    int i;
    for (i = 0; i < len; i++) {
        dst[i] = src[len - 1 - i];
    }
    dst[len] = '\0';
}

void format_reverse(char *buf, const char *val)
{
    int len = (int)strlen(val);
    int i, j = 0;
    char tmp[PROTO_MAX_FRAME_LEN];
    for (i = 0; i < len; i++) {
        tmp[i] = val[len - 1 - i];
    }
    tmp[len] = '\0';

    for (i = 0; i < len; i++) {
        buf[j++] = tmp[i];
    }
    buf[j] = '\0';
}

void respond(const char *resp)
{
    UARTStringPutNonBlocking((const unsigned char *)resp);
    UARTStringPutNonBlocking((const unsigned char *)"\r\n");
}

void respond_error(const char *err)
{
    respond(err);
}

void respond_ok_data(const char *data)
{
    char buf[PROTO_MAX_FRAME_LEN];
    sprintf(buf, "%s %s", OK_STR, data);
    respond(buf);
}

void respond_ok(void)
{
    respond(OK_STR);
}

// ---- 大小写无关的缩写匹配 ----
bool match_abbr(const char *input, const char *pattern)
{
    int i = 0, j = 0;
    while (input[i] != '\0' && pattern[j] != '\0') {
        if (toupper((unsigned char)input[i]) != toupper((unsigned char)pattern[j])) {
            return false;
        }
        i++;
        j++;
    }
    if (input[i] != '\0') {
        return false;
    }
    while (pattern[j] != '\0') {
        if (pattern[j] >= 'A' && pattern[j] <= 'Z') {
            return false;
        }
        j++;
    }
    return true;
}

// ---- 帧解析 ----
bool parse_frame(const char *raw, char *cmd, int cmd_size,
                 char args[PROTO_ARG_MAX][PROTO_MAX_FRAME_LEN/2], int *argc)
{
    static char tmp[PROTO_MAX_FRAME_LEN + 1];
    char *token;
    int i;

	memset(tmp, 0, sizeof(tmp));
    cmd[0] = '\0';
    *argc = 0;

    if (strlen(raw) > PROTO_MAX_FRAME_LEN) {
        respond_error(ERROR_LEN_STR);
        return false;
    }

    strncpy(tmp, raw, PROTO_MAX_FRAME_LEN);
    tmp[PROTO_MAX_FRAME_LEN] = '\0';

    token = strtok(tmp, " :\t");
    if (token == NULL) {
        return false;
    }

    strncpy(cmd, token, cmd_size - 1);
    cmd[cmd_size - 1] = '\0';

    while ((token = strtok(NULL, " \t")) != NULL) {
        if (*argc >= PROTO_ARG_MAX) {
            respond_error(ERROR_SYNTAX_STR);
            return false;
        }
        strncpy(args[*argc], token, (PROTO_MAX_FRAME_LEN/2) - 1);
        args[*argc][PROTO_MAX_FRAME_LEN/2 - 1] = '\0';
        (*argc)++;
    }

    return true;
}

// ---- 命令处理主入口 ----
void process_command(const char *raw)
{
    static char cmd[PROTO_MAX_FRAME_LEN];
    static char args[PROTO_ARG_MAX][PROTO_MAX_FRAME_LEN/2];
    int argc = 0;

    memset(cmd, 0, sizeof(cmd));
    memset(args, 0, sizeof(args));

    if (!parse_frame(raw, cmd, sizeof(cmd), args, &argc)) {
        return;
    }

    if (cmd[0] != '*') {
        respond_error(ERROR_SYNTAX_STR);
        return;
    }

    if (match_abbr(cmd, "*RST")) {
        cmd_RST();
    } else if (match_abbr(cmd, "*SET")) {
        cmd_SET(args, argc);
    } else if (match_abbr(cmd, "*GET")) {
        cmd_GET(args, argc);
    } else if (match_abbr(cmd, "*PING")) {
        cmd_PING();
    } else {
        respond_error(ERROR_SYNTAX_STR);
    }
}

// ---- *RST 实现 ----
void cmd_RST(void)
{
    system_date.year = 2026;
    system_date.month = 6;
    system_date.day = 1;
    system_time.hour = 12;
    system_time.min = 0;
    system_time.sec = 0;
    display_on = true;
    display_format = FORMAT_LEFT;
	user_msg_active = 0;
    memset(user_msg, 0, sizeof(user_msg));
    msg_scroll_offset = 0;
    scroll_speed = 500;
	remote_beep_ms = 0;

    if (system_mode == MODE_SETTING) {
        system_mode = MODE_SHOW_TIME;
    }

    show_time();
    respond_ok();
}

// ---- *SET 实现 ----
void cmd_SET(char args[PROTO_ARG_MAX][PROTO_MAX_FRAME_LEN/2], int argc)
{
    char type_str[PROTO_MAX_FRAME_LEN/2] = {0};
    int i = 0;

    if (argc < 1) {
        respond_error(ERROR_SYNTAX_STR);
        return;
    }

    strncpy(type_str, args[0], sizeof(type_str) - 1);
    str_toupper(type_str);

    // ---- *SET:DATE ----
    if (match_abbr(type_str, "DATE")) {
		int v;
        int idx = 1;
		date_t new_date = system_date;

        while (idx < argc) {
            char kw[PROTO_MAX_FRAME_LEN/2] = {0};
            strncpy(kw, args[idx], sizeof(kw) - 1);
            kw[sizeof(kw) - 1] = '\0';
            str_toupper(kw);

            if (match_abbr(kw, "YEAR")) {
                idx++;
                if (idx >= argc) { respond_error(ERROR_PARAM_STR); return; }
                v = (int)strtol(args[idx], NULL, 10);
                if (v < 1960 || v > 2099) { respond_error(ERROR_RANGE_STR); return; }
                                new_date.year = (uint16_t)v;
            } else if (match_abbr(kw, "MONTH")) {
                idx++;
                if (idx >= argc) { respond_error(ERROR_PARAM_STR); return; }
                v = (int)strtol(args[idx], NULL, 10);
                if (v < 1 || v > 12) { respond_error(ERROR_RANGE_STR); return; }
                                new_date.month = (uint8_t)v;
            } else if (match_abbr(kw, "DATE")) {
                idx++;
                if (idx >= argc) { respond_error(ERROR_PARAM_STR); return; }
                v = (int)strtol(args[idx], NULL, 10);
                if (v < 1 || v > 31) { respond_error(ERROR_RANGE_STR); return; }
                                new_date.day = (uint8_t)v;
            } else {
                respond_error(ERROR_SYNTAX_STR);
                return;
            }
            idx++;
        }

        if (!is_valid_date(new_date)) {
            respond_error(ERROR_RANGE_STR);
            return;
        }

		system_date = new_date;
        respond_ok();
        {
            static char buf[16];
            sprintf(buf, "%04d.%02d.%02d", system_date.year, system_date.month, system_date.day);
            evt_send_edit("DATE", buf);
        }
        if (system_mode == MODE_SHOW_TIME) {
            show_time();
        } else if (system_mode == MODE_SHOW_DATE_1 || system_mode == MODE_SHOW_DATE_2) {
            show_date_1();
        }
        return;
    }

    // ---- *SET:TIME ----
    if (match_abbr(type_str, "TIME")) {
		int v;
        int idx = 1;
        time_t new_time = system_time;

        while (idx < argc) {
            char kw[PROTO_MAX_FRAME_LEN/2];
            strncpy(kw, args[idx], sizeof(kw) - 1);
            kw[sizeof(kw) - 1] = '\0';
            str_toupper(kw);

            if (match_abbr(kw, "HOUR")) {
                idx++;
                if (idx >= argc) { respond_error(ERROR_PARAM_STR); return; }
                v = (int)strtol(args[idx], NULL, 10);
                if (v < 0 || v > 23) { respond_error(ERROR_RANGE_STR); return; }
                new_time.hour = (uint8_t)v;
            } else if (match_abbr(kw, "MIN")) {
                idx++;
                if (idx >= argc) { respond_error(ERROR_PARAM_STR); return; }
                v = (int)strtol(args[idx], NULL, 10);
                if (v < 0 || v > 59) { respond_error(ERROR_RANGE_STR); return; }
                new_time.min = (uint8_t)v;
            } else if (match_abbr(kw, "SEC")) {
                idx++;
                if (idx >= argc) { respond_error(ERROR_PARAM_STR); return; }
                v = (int)strtol(args[idx], NULL, 10);
                if (v < 0 || v > 59) { respond_error(ERROR_RANGE_STR); return; }
                new_time.sec = (uint8_t)v;
            } else {
                respond_error(ERROR_SYNTAX_STR);
                return;
            }
            idx++;
        }

        if (!is_valid_time(new_time)) {
            respond_error(ERROR_RANGE_STR);
            return;
        }

		system_time = new_time;
        respond_ok();
        {
            static char buf[16];
            sprintf(buf, "%02d.%02d.%02d", system_time.hour, system_time.min, system_time.sec);
            evt_send_edit("TIME", buf);
        }
        if (system_mode == MODE_SHOW_TIME) {
            show_time();
        }
        return;
    }

    // ---- *SET:ALARM ----
    if (match_abbr(type_str, "ALARM")) {
		int v;
        int idx = 1;
                time_t new_alarm = alarm_time;

        while (idx < argc) {
            char kw[PROTO_MAX_FRAME_LEN/2];
            strncpy(kw, args[idx], sizeof(kw) - 1);
            kw[sizeof(kw) - 1] = '\0';
            str_toupper(kw);

            if (match_abbr(kw, "OFF")) {
                alarming = 0;
                Buzzer_Off();
				idx++;
            } else if (match_abbr(kw, "HOUR")) {
                idx++;
                if (idx >= argc) { respond_error(ERROR_PARAM_STR); return; }
                v = (int)strtol(args[idx], NULL, 10);
                if (v < 0 || v > 23) { respond_error(ERROR_RANGE_STR); return; }
                new_alarm.hour = (uint8_t)v;
                idx++;
            } else if (match_abbr(kw, "MIN")) {
                idx++;
                if (idx >= argc) { respond_error(ERROR_PARAM_STR); return; }
                v = (int)strtol(args[idx], NULL, 10);
                if (v < 0 || v > 59) { respond_error(ERROR_RANGE_STR); return; }
                new_alarm.min = (uint8_t)v;
                idx++;
            } else if (match_abbr(kw, "SEC")) {
                idx++;
                if (idx >= argc) { respond_error(ERROR_PARAM_STR); return; }
                v = (int)strtol(args[idx], NULL, 10);
                if (v < 0 || v > 59) { respond_error(ERROR_RANGE_STR); return; }
                new_alarm.sec = (uint8_t)v;
                idx++;
            } else {
                respond_error(ERROR_SYNTAX_STR);
                return;
            }
        }

        alarm_time = new_alarm;
        respond_ok();
        return;
    }

    // ---- *SET:DISPlay ----
    if (match_abbr(type_str, "DISP")) {
		char val[PROTO_MAX_FRAME_LEN/2];
        if (argc < 2) { respond_error(ERROR_PARAM_STR); return; }
        strncpy(val, args[1], sizeof(val) - 1);
        val[sizeof(val) - 1] = '\0';
        str_toupper(val);
        if (strcmp(val, "ON") == 0) {
            display_on = true;
            respond_ok();
        } else if (strcmp(val, "OFF") == 0) {
            display_on = false;
            seg_clear();
            led_on(0x00);
            respond_ok();
        } else {
            respond_error(ERROR_PARAM_STR);
        }
        return;
    }

    // ---- *SET:FORMAT ----
    if (match_abbr(type_str, "FORMAT")) {
		char val[PROTO_MAX_FRAME_LEN/2];
        if (argc < 2) { respond_error(ERROR_PARAM_STR); return; }        
        strncpy(val, args[1], sizeof(val) - 1);
        val[sizeof(val) - 1] = '\0';
        str_toupper(val);
        if (strcmp(val, "LEFT") == 0) {
            display_format = FORMAT_LEFT;
            respond_ok();
        } else if (strcmp(val, "RIGHT") == 0) {
            display_format = FORMAT_RIGHT;
            respond_ok();
        } else {
            respond_error(ERROR_PARAM_STR);
        }
        return;
    }

    // ---- *SET:MSG ----
    if (match_abbr(type_str, "MSG")) {
		int total_len = 0;
        if (argc < 2) { respond_error(ERROR_PARAM_STR); return; }
        for (i = 1; i < argc; i++) {
            total_len += (int)strlen(args[i]) + 1;
        }
        if (total_len > PROTO_MSG_MAX_LEN + 1) {
            respond_error(ERROR_LEN_STR);
            return;
        }
		memset(user_msg, 0, sizeof(user_msg));
        for (i = 1; i < argc; i++) {
            if (i > 1) strcat(user_msg, " ");
            strcat(user_msg, args[i]);
        }
        user_msg_active = 1;
        msg_scroll_offset = 0;
        last_msg_scroll_tick = systick_count;

        /* ≤8位静态显示; >8位进入滚动 */
        if ((int)strlen(user_msg) > DISP_LEN) {
            seg_set_display(user_msg);
        } else {
            seg_set_display(user_msg);
        }
        respond_ok();
        return;
    }

    // ---- *SET:BEEP ----
    if (match_abbr(type_str, "BEEP")) {
		int ms = (int)strtol(args[1], NULL, 10);
        if (argc < 2) { respond_error(ERROR_PARAM_STR); return; }
        if (ms < 10 || ms > 5000) {
            respond_error(ERROR_RANGE_STR);
            return;
        }
        remote_beep_ms = (uint32_t)ms;
        remote_beep_start_tick = systick_count;
        Buzzer_On();
        respond_ok();
        return;
    }

    // ---- *SET:LED ----
    if (match_abbr(type_str, "LED")) {
		uint8_t val = (uint8_t)strtol(args[1], NULL, 16);
        if (argc < 2) { respond_error(ERROR_PARAM_STR); return; }
        led_on(val);
        respond_ok();
        return;
    }

    // ---- *SET:KEY ----
    if (match_abbr(type_str, "KEY")) {
		char kw[PROTO_MAX_FRAME_LEN/2] = {0};
		KEY_EVENT ev;

        if (argc < 2) { respond_error(ERROR_PARAM_STR); return; }
        strncpy(kw, args[1], sizeof(kw) - 1);
        kw[sizeof(kw) - 1] = '\0';
        str_toupper(kw);

        ev.state = KEY_TAP;
        ev.source = OTHER;

        if (strcmp(kw, "FUNC") == 0)        { ev.key = KEY_FUNC; }
        else if (strcmp(kw, "SHIFT") == 0)  { ev.key = KEY_SHIFT; }
        else if (strcmp(kw, "ADD") == 0)    { ev.key = KEY_ADD; }
        else if (strcmp(kw, "SAVE") == 0)   { ev.key = KEY_SAVE; }
        else if (strcmp(kw, "DISP") == 0)   { ev.key = KEY_DISP; }
        else if (strcmp(kw, "SPEED") == 0)  { ev.key = KEY_SPEED; }
        else if (strcmp(kw, "FORMAT") == 0) { ev.key = KEY_FORMAT; }
        else if (strcmp(kw, "EXT") == 0)    { ev.key = KEY_EXT; }
        else if (strcmp(kw, "USER1") == 0)  { ev.key = KEY_USER1; }
        else if (strcmp(kw, "USER2") == 0)  { ev.key = KEY_USER2; }
        else {
            respond_error(ERROR_PARAM_STR);
            return;
        }

        key_cb[(ev.key) - 1](ev);
        respond_ok();
        return;
    }

    // ---- *SET:MODE (扩展) ----
    if (match_abbr(type_str, "MODE")) {
		char val[PROTO_MAX_FRAME_LEN/2];
        if (argc < 2) { respond_error(ERROR_PARAM_STR); return; }
        
        strncpy(val, args[1], sizeof(val) - 1);
        val[sizeof(val) - 1] = '\0';
        str_toupper(val);
        if (strcmp(val, "DAY") == 0 || strcmp(val, "NIGHT") == 0) {
            respond_ok();
            evt_send_mode(val);
        } else {
            respond_error(ERROR_PARAM_STR);
        }
        return;
    }

    respond_error(ERROR_SYNTAX_STR);
}

// ---- *GET 实现 ----
void cmd_GET(char args[PROTO_ARG_MAX][PROTO_MAX_FRAME_LEN/2], int argc)
{
    char type_str[PROTO_MAX_FRAME_LEN/2] = {0};
    char data[PROTO_MAX_FRAME_LEN] = {0};

    if (argc < 1) {
        respond_error(ERROR_SYNTAX_STR);
        return;
    }

    strncpy(type_str, args[0], sizeof(type_str) - 1);
    str_toupper(type_str);

    if (match_abbr(type_str, "DATE")) {
        sprintf(data, "%04d.%02d.%02d", system_date.year, system_date.month, system_date.day);
    } else if (match_abbr(type_str, "TIME")) {
        sprintf(data, "%02d.%02d.%02d", system_time.hour, system_time.min, system_time.sec);
    } else if (match_abbr(type_str, "ALARM")) {
        sprintf(data, "%02d.%02d.%02d", alarm_time.hour, alarm_time.min, alarm_time.sec);
    } else if (match_abbr(type_str, "DISP")) {
        strcpy(data, display_on ? "ON" : "OFF");
    } else if (match_abbr(type_str, "FORMAT")) {
        strcpy(data, (display_format == FORMAT_LEFT) ? "LEFT" : "RIGHT");
    } else {
        respond_error(ERROR_SYNTAX_STR);
        return;
    }

    if (display_format == FORMAT_RIGHT) {
        char rev[PROTO_MAX_FRAME_LEN];
        str_reverse(rev, data, (int)strlen(data));
        respond_ok_data(rev);
    } else {
        respond_ok_data(data);
    }
}

// ---- *PING 实现 ----
void cmd_PING(void)
{
    char buf[PROTO_MAX_FRAME_LEN];
    sprintf(buf, "*PONG %lu", systick_count / SYSTICK_FREQUENCY);
    respond(buf);
}

// ---- 主动上报函数 ----
void evt_send_edit(const char *type, const char *value)
{
    char buf[PROTO_MAX_FRAME_LEN];
    sprintf(buf, "*EVT:EDIT %s %s", type, value);
    respond(buf);
}

void evt_send_disp(void)
{
    char display_str[9];
    uint8_t dp_bits = 0;
    int i;
	char buf[PROTO_MAX_FRAME_LEN];

    for (i = 0; i < DISP_LEN; i++) {
        uint8_t seg = seg_display_buffer[i];
        bool is_dp = (seg & 0x80) ? true : false;
        uint8_t glyph = seg & 0x7F;
        display_str[i] = seg7_glyph_to_char(glyph);
        if (is_dp) {
            dp_bits |= (uint8_t)(1 << i);
        }
    }
    display_str[DISP_LEN] = '\0';

    sprintf(buf, "*EVT:DISP %s %02X", display_str, dp_bits);
    respond(buf);
}

void evt_send_led(void)
{
    uint32_t val = I2C0_ReadByte(PCA9557_I2CADDR, PCA9557_INPUT);
    uint8_t led_val = (uint8_t)((~val) & 0xFF);
    char buf[PROTO_MAX_FRAME_LEN];
    sprintf(buf, "*EVT:LED %02X", led_val);
    respond(buf);
}

void evt_send_key(const char *name)
{
    char buf[PROTO_MAX_FRAME_LEN];
    sprintf(buf, "*EVT:KEY %s", name);
    respond(buf);
}

void evt_send_alarm(void)
{
    respond("*EVT:ALARM");
}

void evt_send_alarm_off(void)
{
    respond("*EVT:ALARM_OFF");
}

void evt_send_mode(const char *state)
{
    char buf[PROTO_MAX_FRAME_LEN];
    sprintf(buf, "*EVT:MODE %s", state);
    respond(buf);
}

/* ========================= GPIO function ================================== */

void S800_GPIO_Init(void)
{
	SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOF);						//Enable PortF
	while(!SysCtlPeripheralReady(SYSCTL_PERIPH_GPIOF));			//Wait for the GPIO moduleF ready
	SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOJ);						//Enable PortJ	
	while(!SysCtlPeripheralReady(SYSCTL_PERIPH_GPIOJ));			//Wait for the GPIO moduleJ ready	
	SysCtlPeripheralEnable(SYSCTL_PERIPH_GPION);						//Enable PortN	
	while(!SysCtlPeripheralReady(SYSCTL_PERIPH_GPION));			//Wait for the GPIO moduleN ready		
	SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOK);
	while(!SysCtlPeripheralReady(SYSCTL_PERIPH_GPIOK));
	SysCtlPeripheralEnable(SYSCTL_PERIPH_PWM0);
	while(!SysCtlPeripheralReady(SYSCTL_PERIPH_PWM0));
	
	GPIOPinTypeGPIOOutput(GPIO_PORTF_BASE, GPIO_PIN_0);			//Set PF0 as Output pin
	GPIOPinTypeGPIOOutput(GPIO_PORTN_BASE, GPIO_PIN_0);			//Set PN0 as Output pin

	GPIOPinTypeGPIOInput(GPIO_PORTJ_BASE,GPIO_PIN_0 | GPIO_PIN_1);//Set the PJ0,PJ1 as input pin
	GPIOPadConfigSet(GPIO_PORTJ_BASE,GPIO_PIN_0 | GPIO_PIN_1,GPIO_STRENGTH_2MA,GPIO_PIN_TYPE_STD_WPU);

	GPIOPinConfigure(GPIO_PK5_M0PWM7);
    GPIOPinTypePWM(GPIO_PORTK_BASE, GPIO_PIN_5);
}

/* ========================= PWM function ================================== */

void S800_PWM_Init(void)
{
	pwm_period = ui32SysClock / BUZZER_FREQ;
    PWMClockSet(PWM0_BASE, PWM_SYSCLK_DIV_1);
    PWMGenConfigure(PWM0_BASE, PWM_GEN_3, PWM_GEN_MODE_DOWN | PWM_GEN_MODE_NO_SYNC);
    PWMGenPeriodSet(PWM0_BASE, PWM_GEN_3, pwm_period);
    PWMPulseWidthSet(PWM0_BASE, PWM_OUT_7, pwm_period / 2); // 50%占空比

    // 默认关闭蜂鸣器
    PWMOutputState(PWM0_BASE, PWM_OUT_7_BIT, false);
    PWMGenEnable(PWM0_BASE, PWM_GEN_3);
}

void Buzzer_On(void)
{
    PWMOutputState(PWM0_BASE, PWM_OUT_7_BIT, true);
	buzzer_state = true;
}

void Buzzer_Off(void)
{
    PWMOutputState(PWM0_BASE, PWM_OUT_7_BIT, false);
	buzzer_state = false;
}

void Buzzer_Toggle(void)
{
    buzzer_state = !buzzer_state;
    PWMOutputState(PWM0_BASE, PWM_OUT_7_BIT, buzzer_state);
}

/* ========================= I2C function ================================== */

void S800_I2C0_Init(void)
{
	uint8_t result;
	SysCtlPeripheralEnable(SYSCTL_PERIPH_I2C0);
	SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOB);
	GPIOPinConfigure(GPIO_PB2_I2C0SCL);
	GPIOPinConfigure(GPIO_PB3_I2C0SDA);
	GPIOPinTypeI2CSCL(GPIO_PORTB_BASE, GPIO_PIN_2);
	GPIOPinTypeI2C(GPIO_PORTB_BASE, GPIO_PIN_3);

	I2CMasterInitExpClk(I2C0_BASE,ui32SysClock, true);										//config I2C0 400k
	I2CMasterEnable(I2C0_BASE);	

	result = I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_CONFIG_PORT0,0xFF);		    //config port 0 as input
	result = I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_CONFIG_PORT1,0x0);			//config port 1 as output
	result = I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_CONFIG_PORT2,0x0);			//config port 2 as output
	result = I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT1,0x00);
	result = I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT2,0x00);

	result = I2C0_WriteByte(PCA9557_I2CADDR,PCA9557_CONFIG,0x00);				//config port as output
	result = I2C0_WriteByte(PCA9557_I2CADDR,PCA9557_OUTPUT,0xFF);				//turn off the LED1-8
	
}

uint8_t I2C0_WriteByte(uint8_t DevAddr, uint8_t RegAddr, uint8_t WriteData)
{
	uint8_t rop;
	while(I2CMasterBusy(I2C0_BASE)){};
	I2CMasterSlaveAddrSet(I2C0_BASE, DevAddr, false);

	I2CMasterDataPut(I2C0_BASE, RegAddr);
	I2CMasterControl(I2C0_BASE, I2C_MASTER_CMD_BURST_SEND_START);
	while(I2CMasterBusy(I2C0_BASE)){};
	rop = (uint8_t)I2CMasterErr(I2C0_BASE);

	I2CMasterDataPut(I2C0_BASE, WriteData);
	I2CMasterControl(I2C0_BASE, I2C_MASTER_CMD_BURST_SEND_FINISH);
	while(I2CMasterBusy(I2C0_BASE)){};
	rop = (uint8_t)I2CMasterErr(I2C0_BASE);

	return rop;
}

uint32_t I2C0_ReadByte(uint8_t DevAddr, uint8_t RegAddr){
	uint32_t value,rop;

	while(I2CMasterBusy(I2C0_BASE));

	I2CMasterSlaveAddrSet(I2C0_BASE, DevAddr, false);
	I2CMasterDataPut(I2C0_BASE, RegAddr);
	I2CMasterControl(I2C0_BASE,I2C_MASTER_CMD_BURST_SEND_START);
	while(I2CMasterBusy(I2C0_BASE));
	rop = (uint8_t)I2CMasterErr(I2C0_BASE);
	
	//receive data
	I2CMasterSlaveAddrSet(I2C0_BASE, DevAddr, true);
	I2CMasterControl(I2C0_BASE,I2C_MASTER_CMD_SINGLE_RECEIVE);
	while(I2CMasterBusy(I2C0_BASE));
	rop = (uint8_t)I2CMasterErr(I2C0_BASE);

	value = I2CMasterDataGet(I2C0_BASE);

	return value;
}

void led_on(uint8_t bitmap){
	I2C0_WriteByte(PCA9557_I2CADDR, PCA9557_OUTPUT, ~bitmap);
}

/* ========================= 七段数码管显示 ================================== */

void seg_write(uint8_t pos, uint8_t value){
	I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT1,value);			
	I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT2,(uint8_t)(1<<pos));
}

// 更新显示缓存区
void seg_set_display(const char* str){
	int i = 0, j = 0;
	seg_clear();

    while(i < DISP_LEN && str[j] != '\0'){

        char c = str[j];
		c = toupper(c);

        if(c == '.'){
            if(i > 0){
                seg_display_buffer[i - 1] |= 0x80;
            }
            j++;
            continue;
        }

        if(c >= '0' && c <= '9'){
            seg_display_buffer[i] = seg7_digit[c - '0'];
        }
        else if(c >= 'A' && c <= 'Z'){
            seg_display_buffer[i] = seg7_letter[c - 'A'];
        }
        else{
            seg_display_buffer[i] = 0x00;
        }

        i++;
        j++;
    }

    while(i < DISP_LEN){
        seg_display_buffer[i++] = 0x00;
    }
}

void seg_clear(void){
	memset(seg_display_buffer, 0, sizeof(seg_display_buffer));
}

void seg_refresh(void)				// 数码管刷新任务
{
	I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT2,(uint8_t)0x00);
	I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT1,seg_display_buffer[seg_display_pos]);			
	I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT2,(uint8_t)(1<<seg_display_pos));
	seg_display_pos = (seg_display_pos + 1) % 8;
}

void boot_display(void) {
    static uint8_t boot_step = 0;
    int i;

    switch(boot_step) {
        case 0: // 1. 8位数码管+8位LED全亮
			memset(seg_display_buffer, 0xFF, DISP_LEN);
            led_on(0xFF);
            break;
            
        case 1: // 全灭
            seg_clear();
            led_on(0x00);
            break;
            
        case 2: // 2. 显示学号后8位，LED同步闪烁（亮）
            seg_set_display(MY_STUDENT_ID);
            led_on(0xFF);
            break;
            
        case 3: // 闪烁（灭）
            seg_clear();
            led_on(0x00);
            break;
            
        case 4: // 3. 显示姓名拼音
            seg_set_display(MY_NAME);
			led_on(0xFF);
            break;
            
        case 5: // 闪烁（灭）
            seg_clear();
            led_on(0x00);
            break;
            
        case 6: // 4. 显示软件版本号
            seg_set_display(FW_VERSION);
			led_on(0xFF);
            break;
            
		case 7: // 进入正常时钟显示
			seg_clear();
			led_on(0x00);
			user_msg_active = 0;
			msg_scroll_offset = 0;
		    system_mode = MODE_SHOW_TIME;
		    break;
            
        default: 
            break;
    }
    
    if (boot_step < 8) {
        boot_step++;
    }
}

/* ========================= 电子时钟功能代码 ================================== */

bool date_equal(date_t date1, date_t date2)
{
    return (date1.year == date2.year) && (date1.month == date2.month) && (date1.day == date2.day);
}
bool time_equal(time_t time1, time_t time2)
{
    return (time1.hour == time2.hour) && (time1.min == time2.min) && (time1.sec == time2.sec);
}


bool is_leap(uint16_t year) { 
    return (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
}

bool is_valid_date(date_t date) {
	uint8_t days_in_month[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if(date.month < 1 || date.month > 12) return false;
    if(date.day < 1) return false;
    
    if(is_leap(date.year)) days_in_month[1] = 29;

    if(date.day > days_in_month[date.month - 1]) return false;

    return true;
}

bool is_valid_time(time_t time) {
    if(time.hour > 23) return false;
    if(time.min > 59) return false;
    if(time.sec > 59) return false;
    return true;
}

// --- 带指针参数的 add 函数：返回 true 表示进位 ---

bool add_sec(time_t *time) {
    time->sec++;
    if(time->sec >= 60){
        time->sec = 0;
        return add_min(time);
    }
	return false;
}

bool add_min(time_t *time) {
    time->min++;
    if(time->min >= 60){
        time->min = 0;
        return add_hour(time);
    }
	return false;
}

bool add_hour(time_t *time) {
    time->hour++;
    if(time->hour >= 24){
        time->hour = 0;
        return true;   // 进位到日期
    }
    return false;
}

bool add_day(date_t *date) {
    date->day++;
    if(!is_valid_date(*date)){
        date->day = 1;
        return add_month(date);
    }
	return false;
}

bool add_month(date_t *date) {
    date->month++;
    if(date->month > 12){
        date->month = 1;
        return add_year(date);
    }
	return false;
}

bool add_year(date_t *date) {
    date->year++;
	if(date->year >= 2100){
		date->year = 1960;
		return true;
	}
    return false;
}

// --- 无参 sys 函数：操作全局 system_date / system_time ---

void add_sys_sec(void) {
    if(add_sec(&system_time)) {
        add_sys_day();
    }
}

void add_sys_min(void) {
    if(add_min(&system_time)) {
        add_sys_day();
    }
}

void add_sys_hour(void) {
    if(add_hour(&system_time)) {
        add_sys_day();
    }
}

void add_sys_day(void) {
    add_day(&system_date);
}

void add_sys_month(void) {
    add_month(&system_date);
}

void add_sys_year(void) {
    add_year(&system_date);
}


void show_time(void){
	char buf[16];
	sprintf(buf, "%02d.%02d.%02d", system_time.hour, system_time.min, system_time.sec);
	seg_set_display(buf);
}

void show_date_1(void){
	char buf[16];
	sprintf(buf, "%02d.%02d.%02d", system_date.year%100, system_date.month, system_date.day);
	seg_set_display(buf);
}

void show_date_2(void){
	char buf[16];
	sprintf(buf, "%04d.%02d.%02d", system_date.year, system_date.month, system_date.day);
	seg_set_display(buf);
}

void alarm(void){
    static uint8_t alarm_tick = 0;    

	if(alarm_tick >= 10){
		Buzzer_Off();
		alarming = 0;
		alarm_tick = 0;
		evt_send_alarm_off();
	}else{
		Buzzer_Toggle();
		alarm_tick++;
	}
}


/* =========================== 按键处理 =============================== */

bool key_queue_empty(void)
{
    return (key_queue_head == key_queue_tail);
}
bool key_queue_full(void)
{
    return ((key_queue_tail + 1) % KEY_QUEUE_SIZE == key_queue_head);
}

uint8_t key_push(KEY_EVENT ev){
	uint8_t next = (key_queue_tail + 1) % KEY_QUEUE_SIZE;
   
	if(next == key_queue_head) {
        return (uint8_t)-1; //队列已满，返回-1
    }

    key_queue[key_queue_tail] = ev;
    key_queue_tail = next;
    return (key_queue_tail - 1) % KEY_QUEUE_SIZE;  // 返回插入元素的下标
}

KEY_EVENT *key_pop(void){
	KEY_EVENT *ev;
	if(key_queue_head == key_queue_tail)
		return NULL; // 队列为空

    ev = &key_queue[key_queue_head];
    key_queue_head = (key_queue_head + 1) % KEY_QUEUE_SIZE;
    return ev; // 返回队首元素指针
}

/**
	@brief 	按键扫描函数
	@details 	20ms消抖
				按下时间 >800ms 入队长按事件，否则入队短按事件
`*/
void key_scan(void){
	static uint8_t raw;
	static uint8_t last_raw;

	static uint16_t key_pressed_time[8]; 

	uint8_t i;
	KEY_EVENT ev;

	raw = I2C0_ReadByte(TCA6424_I2CADDR, TCA6424_INPUT_PORT0);
	for(i=0; i<8; i++){
		uint8_t mask = (uint8_t)(1<<i);
		if((raw & mask) == 0)		// 按下 
		{
			if(key_pressed_time[i] < KEY_PRESS_TIME){
				key_pressed_time[i] += SYSTICK_FREQUENCY / KEY_SCAN_FREQ;
						}else if(key_pressed_time[i] != 0xFFFF){
				ev.key = i+1;
				ev.state = KEY_PRESS;
				ev.source = ON_BORAD;
				key_push(ev);
				key_pressed_time[i] = 0xFFFF;
			}
		}else if((last_raw & mask) == 0){
			if(key_pressed_time[i] == 0xFFFF){
				ev.key = i+1;
				ev.state = KEY_PRESSUP;
				ev.source = ON_BORAD;
				key_push(ev);
			}else if(key_pressed_time[i] > KEY_DEBOUNCE_TIME){
				ev.key = i+1;
				ev.state = KEY_TAP;
				ev.source = ON_BORAD;
				key_push(ev);
			}
			
			key_pressed_time[i] = 0;
		}
	}
	
	last_raw = raw;
}

/**
	@brief 按键事件处理函数
	@details 从按键事件队列中取事件，并分发到各自的回调函数中处理
*/
void key_event_dispatch(void){
	static KEY_EVENT *ev;
	ev = key_pop();
	if(ev == NULL) return;

	// 物理按键按下时上报 *EVT:KEY（仅在 ON_BORAD 来源时）
	if(ev->source == ON_BORAD) {
		static const char *key_names[] = {
			"FUNC", "SHIFT", "ADD", "SAVE", "DISP", "SPEED", "FORMAT", "EXT", "USER1", "USER2"
		};
		evt_send_key(key_names[(ev->key) - 1]);
	}

	// 滚动消息期间，按任意键（除FUNC/ADD编辑键外）中断流水回到时钟
	if (user_msg_active && (int)strlen(user_msg) > DISP_LEN) {
		if ((ev->key != KEY_FUNC) && (ev->key != KEY_ADD)) {
			user_msg_active = 0;
			msg_scroll_offset = 0;
			if (system_mode == MODE_SHOW_TIME) show_time();
			else if (system_mode == MODE_SHOW_DATE_1) show_date_1();
			else if (system_mode == MODE_SHOW_DATE_2) show_date_2();
			return;
		}
	}

	key_cb[(ev->key)-1](*ev);
}

/* -------------------- 按键回调函数 -------------------------- */

void KEY_FUNC_Cb(KEY_EVENT ev)
{
    // Implement KEY_FUNC handling logic here
	char str[32] = {0};
	switch (ev.state){
		case KEY_TAP:
			if(alarming == 1){
				alarming = 0;
				Buzzer_Off();
				evt_send_alarm_off();
				break;
			}
			if (system_mode != MODE_SETTING){
				temp_mode = system_mode;
				system_mode = MODE_SETTING;

				setting = SET_DATE;
				subitem = SET_YEAR_HOUR;

				temp_date = system_date;
				temp_time = system_time;
				temp_alarm = alarm_time;

				last_blink_tick = systick_count;
				blinker = true;
				setting_timeout_timer = systick_count;

				sprintf(str, "%04d.%02d.%02d", temp_date.year, temp_date.month, temp_date.day);
				seg_set_display(str);
				break;
			}

			setting_timeout_timer = systick_count;
			switch(setting){
				case SET_DATE:	setting = SET_TIME;		break;
				case SET_TIME:	setting = SET_ALARM;	break;
				case SET_ALARM:	setting = SET_DATE; 	break;
				default: break;
			}
			subitem = SET_YEAR_HOUR;
			break;

		case KEY_PRESS:
			quit_setting();
			break;

		case KEY_PRESSUP:
		case KEY_IDLE:
		default:
			break;
	}
}
void KEY_SHIFT_Cb(KEY_EVENT ev)
{
    // Implement KEY_SHIFT handling logic here
	switch (ev.state){
		case KEY_TAP:
		case KEY_PRESS:
			if(system_mode != MODE_SETTING) break;

			last_blink_tick = systick_count;
			blinker = true;
			setting_timeout_timer = systick_count;

			switch(subitem){
				case SET_YEAR_HOUR: subitem = SET_MONTH_MIN;	break;
				case SET_MONTH_MIN: subitem = SET_DAY_SEC;		break;
				case SET_DAY_SEC: 	subitem = SET_YEAR_HOUR;	break;
				default: break;
			}
			break;
		case KEY_PRESSUP:
		case KEY_IDLE:
		default:
			break;
	}
}
void KEY_ADD_Cb(KEY_EVENT ev)
{
	// Implement KEY_ADD handling logic here
	if(system_mode != MODE_SETTING) return;
    
	switch (ev.state){
		case KEY_TAP:
			add_cur_subitem();
			break;
		case KEY_PRESS:
			is_add_pressing = 1;
			break;
		case KEY_PRESSUP:
			is_add_pressing = 0;
			break;
		case KEY_IDLE:
		default:
			break;
	}
}
void KEY_SAVE_Cb(KEY_EVENT ev)
{
    // Implement KEY_SAVE handling logic here
	switch (ev.state){
		case KEY_TAP:
		case KEY_PRESS:
			if(system_mode == MODE_SETTING){
				quit_setting();
			}
			break;
		case KEY_PRESSUP:
		case KEY_IDLE:
		default:
			break;
	}
}
void KEY_DISP_Cb(KEY_EVENT ev)
{
    // Implement KEY_DISP handling logic here
	switch (ev.state){
		case KEY_TAP:
		case KEY_PRESS:
			switch(system_mode){
				case MODE_SHOW_TIME:
					system_mode = MODE_SHOW_DATE_1;
					show_date_1();
					break;
				case MODE_SHOW_DATE_1:
					system_mode = MODE_SHOW_DATE_2;
					show_date_2();
					break;
				case MODE_SHOW_DATE_2:
					system_mode = MODE_SHOW_TIME;
					show_time();
					break;
			}
			break;
		case KEY_PRESSUP:
		case KEY_IDLE:
		default:
			break;
	}
}
void KEY_SPEED_Cb(KEY_EVENT ev)
{
    // 滚动速度切换: 250ms / 500ms
	switch (ev.state){
		case KEY_TAP:
			scroll_speed = (scroll_speed == 500) ? 250 : 500;
			break;
		case KEY_PRESS:
		case KEY_PRESSUP:
		case KEY_IDLE:
		default:
			break;
	}
}
void KEY_FORMAT_Cb(KEY_EVENT ev)
{
    // 滚动方向切换: LEFT(0) / RIGHT(1)
	switch (ev.state){
		case KEY_TAP:
		case KEY_PRESS:
			display_format = (display_format == FORMAT_LEFT) ? FORMAT_RIGHT : FORMAT_LEFT;
			break;
		case KEY_PRESSUP:
		case KEY_IDLE:
		default:
			break;
	}
}
void KEY_EXT_Cb(KEY_EVENT ev)
{
    // Implement KEY_EXT handling logic here
	switch (ev.state){
		case KEY_TAP:
		case KEY_PRESS:
		case KEY_PRESSUP:
		case KEY_IDLE:
		default:
			break;
	}
}
void KEY_USER1_Cb(KEY_EVENT ev)
{
    // Implement KEY_USER1 handling logic here
	switch (ev.state){
		case KEY_TAP:
		case KEY_PRESS:
		case KEY_PRESSUP:
		case KEY_IDLE:
		default:
			break;
	}
}
void KEY_USER2_Cb(KEY_EVENT ev)
{
    // Implement KEY_USER2 handling logic here
	switch (ev.state){
		case KEY_TAP:
		case KEY_PRESS:
		case KEY_PRESSUP:
		case KEY_IDLE:
		default:
			break;
	}
}




/* ========================= Interrupt function ================================== */

void S800_Int_Init(void)
{
	SysTickPeriodSet(ui32SysClock/SYSTICK_FREQUENCY);
	SysTickEnable();
	SysTickIntEnable();

	UARTIntEnable(UART0_BASE, UART_INT_RX | UART_INT_RT);
	IntEnable(INT_UART0);

   	IntMasterEnable();
}

void SysTick_Handler(void)
{
	static volatile uint32_t cnt_2ms, cnt_10ms,  cnt_100ms,  cnt_1s;

	systick_count++;
	flag_1ms = 1;
	if(++cnt_2ms == 2){
		cnt_2ms = 0;
		flag_2ms = 1;
	}
	if(++cnt_10ms == 10){
		cnt_10ms = 0;
		flag_10ms = 1;
	}
	if(++cnt_100ms == 100){
		cnt_100ms = 0;
		flag_100ms = 1;
	}
	if(++cnt_1s == 1000){
		cnt_1s = 0;
		flag_1s = 1;
	}
}

void UART0_Handler(void)
{
	static uint32_t RxBufIndex = 0;
	uint32_t ui32Status;
	ui32Status = UARTIntStatus(UART0_BASE, true);
	UARTIntClear(UART0_BASE, ui32Status);

	while(UARTCharsAvail(UART0_BASE))
	{
		char ch = UARTCharGetNonBlocking(UART0_BASE);
		if(RxBufIndex < UART_BUFFER_SIZE - 1){
			RxBuf[RxBufIndex++] = ch;
			if (ch == '\r' || ch == '\n') {
				RxBuf[RxBufIndex] = '\0';
				RxBufIndex = 0;
				RxEndFlag = 1;
			}
		} else {
			RxBufIndex = 0;
		}
	}

	if((ui32Status & UART_INT_RT)){
		RxBuf[RxBufIndex] = '\0';
		RxBufIndex = 0;	
		RxEndFlag = 1;
	}
}

/* ======================= 系统显示模式&设置项 ======================= */

void add_cur_subitem(void){
	char str[32] = {0};

	if(system_mode != MODE_SETTING) return;

	last_blink_tick = systick_count;
	blinker = true;
	setting_timeout_timer = systick_count;
	switch(setting){
        case SET_DATE:
            switch(subitem){
                case SET_YEAR_HOUR:
                    add_year(&temp_date);
                    break;
                case SET_MONTH_MIN:
                    add_month(&temp_date);
                    break;
                case SET_DAY_SEC:
                    add_day(&temp_date);
                    break;
                default:
                    break;
			}
			sprintf(str, "%04d.%02d.%02d", temp_date.year, temp_date.month, temp_date.day);
            break;
        case SET_TIME:
            switch(subitem){
                case SET_YEAR_HOUR:
                    add_hour(&temp_time);
                    break;
                case SET_MONTH_MIN:
                    add_min(&temp_time);
                    break;
                case SET_DAY_SEC:
                    add_sec(&temp_time);
                    break;
                default:
                    break;
			}
			sprintf(str, "%02d.%02d.%02d", temp_time.hour, temp_time.min, temp_time.sec);
            break;
        case SET_ALARM:
            switch(subitem){
                case SET_YEAR_HOUR:
                    add_hour(&temp_alarm);
                    break;
                case SET_MONTH_MIN:
                    add_min(&temp_alarm);
                    break;
                case SET_DAY_SEC:
                    add_sec(&temp_alarm);
                    break;
                default:
                    break;
            }
			sprintf(str, "%02d.%02d.%02d", temp_alarm.hour, temp_alarm.min, temp_alarm.sec);
            break;
        default:
            break;
    }
	seg_set_display(str);
}

void blink_cur_subitem(void){
	char str[32] = {0};


	if(system_mode != MODE_SETTING) return;

	if(systick_count - setting_timeout_timer >= 5000){
		quit_setting();
		return;
	}

	if(systick_count - last_blink_tick >= 500){
		switch(setting){
			case SET_DATE:
				sprintf(str, "%04d.%02d.%02d", temp_date.year, temp_date.month, temp_date.day);
				if(!blinker){
					switch(subitem){
						case SET_YEAR_HOUR:
							str[0] = ' ';
							str[1] = ' ';
							str[2] = ' ';
							str[3] = ' ';
							break;
						case SET_MONTH_MIN:
							str[5] = ' ';
							str[6] = ' ';
							break;
						case SET_DAY_SEC:
							str[8] = ' ';
							str[9] = ' ';
							break;
						default:
							break;
					}
				}
				break;
			case SET_TIME:
				sprintf(str, "%02d.%02d.%02d", temp_time.hour, temp_time.min, temp_time.sec);
				if(!blinker){
					switch(subitem){
						case SET_YEAR_HOUR:
							str[0] = ' ';
							str[1] = ' ';
							break;
						case SET_MONTH_MIN:
							str[3] = ' ';
							str[4] = ' ';
							break;
						case SET_DAY_SEC:
							str[6] = ' ';
							str[7] = ' ';
							break;
						default:
							break;
					}
				}
				break;
			case SET_ALARM:
				sprintf(str, "%02d.%02d.%02d", temp_alarm.hour, temp_alarm.min, temp_alarm.sec);
				if(!blinker){
					switch(subitem){
					case SET_YEAR_HOUR:
						str[0] = ' ';
						str[1] = ' ';
						break;
					case SET_MONTH_MIN:
						str[3] = ' ';
						str[4] = ' ';
						break;
					case SET_DAY_SEC:
						str[6] = ' ';
						str[7] = ' ';
						break;
					default:
						break;
					}
				}
				break;
			default:
				break;
		}

		blinker = !blinker;
		last_blink_tick = systick_count;
		seg_set_display(str);
	}
}

void quit_setting(void){
	system_date = temp_date;
	system_time = temp_time;
	alarm_time 	= temp_alarm;

	setting = 0;
	subitem = 0;

	setting_timeout_timer = systick_count;
	blinker = true;

	system_mode = temp_mode;
	switch(system_mode){
		case MODE_SHOW_TIME: 
			show_time(); 
			break; 
		case MODE_SHOW_DATE_1:
			show_date_1();
			break;
		case MODE_SHOW_DATE_2:
			show_date_2();
			break;
		default: break;
	}

}

/* =============== MAIN =============== */

int main(void)
{
	volatile uint16_t i2c_flash_cnt,gpio_flash_cnt;

	uint8_t i;		// for循环使用

	char tmp[UART_BUFFER_SIZE];
	
	ui32SysClock = SysCtlClockFreqSet((SYSCTL_XTAL_16MHZ |SYSCTL_OSC_INT | SYSCTL_USE_PLL |SYSCTL_CFG_VCO_480), 20000000);
	
	S800_GPIO_Init();
	S800_PWM_Init();
	S800_I2C0_Init();
	S800_UART_Init();
	S800_Int_Init();
	
	UARTStringPutNonBlocking("Initialization complete.\r\n");
	/* ============ MAIN LOOP ================ */
	for(;;)
	{	
		if(flag_1s == 1){
			flag_1s = 0;
			if (system_mode != MODE_BOOT){
				add_sys_sec();
			}

			/* 用户消息 ≤8位: 静态显示 2秒后自动退出 */
			if (user_msg_active && (int)strlen(user_msg) <= DISP_LEN) {
				if (systick_count - last_msg_scroll_tick >= 2 * SYSTICK_FREQUENCY) {
					user_msg_active = 0;
					msg_scroll_offset = 0;
				}
			}

			if (!user_msg_active) {
				switch(system_mode){
					case MODE_BOOT: 
						boot_display();
						break;
					case MODE_SHOW_TIME: 
						show_time(); 
						break; 
					case MODE_SHOW_DATE_1:
						show_date_1();
						break;
					case MODE_SHOW_DATE_2:
						show_date_2();
						break;
					case MODE_SETTING:
						break;
					default: break;
				}
			}

			/* 数码管不亮时，显示也需更新缓存(为了心跳上报) */
			if (!display_on) {
				seg_clear();
				led_on(0x00);
			}

			if(time_equal(alarm_time, system_time))	// 闹钟时间到
			{
				alarming = 1;
				evt_send_alarm();
			}
			if(alarming == 1){
				alarm();
			}

			/* 远程蜂鸣超时检查 */
			if (remote_beep_ms > 0) {
				uint32_t elapsed = (systick_count - remote_beep_start_tick) * (1000 / SYSTICK_FREQUENCY);
				if (elapsed >= remote_beep_ms) {
					Buzzer_Off();
					remote_beep_ms = 0;
				}
			}

			/* 1秒心跳：*EVT:DISP 和 *EVT:LED */
			evt_send_disp();
			evt_send_led();
		}
		
		if(flag_2ms == 1){
			flag_2ms = 0;
			seg_refresh();
		}

		if(flag_10ms == 1){
			flag_10ms = 0;

			key_scan();
			while(!key_queue_empty()){
				key_event_dispatch();
			}
		}

		if(flag_100ms == 1){
			flag_100ms = 0;

			/* >8位滚动消息：按scroll_speed速率滚动 */
			if (user_msg_active && (int)strlen(user_msg) > DISP_LEN) {
				int msg_len = (int)strlen(user_msg);
				if (msg_len > 0) {
					if (systick_count - last_msg_scroll_tick >= (uint32_t)(scroll_speed * SYSTICK_FREQUENCY / 1000)) {
						char display_str[DISP_LEN + 1] = {0};
						int j;
						last_msg_scroll_tick = systick_count;
						msg_scroll_offset++;
						for (j = 0; j < DISP_LEN; j++) {
							int pos;
							if (display_format == FORMAT_LEFT) {
								pos = (j + msg_scroll_offset) % msg_len;
							} else {
								pos = (msg_len - 1 - (j + msg_scroll_offset) % msg_len + msg_len) % msg_len;
							}
							display_str[j] = user_msg[pos];
						}
						display_str[DISP_LEN] = '\0';
						seg_set_display(display_str);
						/* 走完一遍后自动退出 */
						if (msg_scroll_offset >= msg_len) {
							user_msg_active = 0;
							msg_scroll_offset = 0;
						}
					}
				}
			}

			if(is_add_pressing == 1){
				add_cur_subitem();
			}
		}

		if(RxEndFlag == 1){
			RxEndFlag = 0;

			strcpy(tmp, (const char *)RxBuf);
			strtok(tmp, "\r\n");
			process_command(tmp);
		}



		blink_cur_subitem();
		
		// if(flag_1s == 1)
		// {
		// 	flag_1s = 0;
		// 	/* 初始化数码管显示 */
		// 	switch(boot_flag){
		// 		case 0:{
		// 			int i;
		// 			for(i=0; i<8; ++i){
		// 				seg_display_buffer[i] = 0xFF;
		// 			}
		// 			break;
		// 		}
		// 		case 2:
		// 			seg_set_display(MY_STUDENT_ID);
		// 			break;
		// 		case 4:
		// 			seg_set_display(MY_NAME);
		// 			break;
		// 		case 6:
		// 			seg_set_display(FW_VERSION);
		// 			break;
		// 		case 1: case 3: case 5: case 7:
		// 			seg_clear();
		// 			break;
		// 		default: break;
		// 	}
		// 	if(boot_flag < 8) boot_flag++;

		// 	clock_tick();
		// }

		// if(flag_5ms == 1){
		// 	flag_5ms == 0;
		// 	/* 数码管刷新 */	
		// 	I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT2,(uint8_t)0x00);
		// 	I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT1,seg_display_buffer[seg_display_pos]);			
		// 	I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT2,(uint8_t)(1<<seg_display_pos));
		// 	seg_display_pos = (seg_display_pos + 1) % 8;
		// }
		// if (systick_10ms_status)
		// {
		// 	systick_10ms_status		= 0;
		// 	if (++gpio_flash_cnt	>= GPIO_FLASHTIME/10)
		// 	{
		// 		gpio_flash_cnt			= 0;
		// 		if (gpio_status)
		// 			GPIOPinWrite(GPIO_PORTF_BASE, GPIO_PIN_0,GPIO_PIN_0 );
		// 		else
		// 			GPIOPinWrite(GPIO_PORTF_BASE, GPIO_PIN_0,0);
		// 		gpio_status					= !gpio_status;
			
		// 	}
		// }
		// if (systick_100ms_status)
		// {
		// 	systick_100ms_status = 0;
		// 	if (++i2c_flash_cnt	>= I2C_FLASHTIME/100)
		// 	{
		// 		i2c_flash_cnt = 0;
		// 		result = I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT1,seg7_digit[cnt+1]);	//write port 1 				
		// 		result = I2C0_WriteByte(TCA6424_I2CADDR,TCA6424_OUTPUT_PORT2,rightshift);	//write port 2
		
		// 		result = I2C0_WriteByte(PCA9557_I2CADDR,PCA9557_OUTPUT,~rightshift);	

		// 		cnt++;
		// 		rightshift= rightshift<<1;

		// 		if (cnt >= 0x8)
		// 		{
		// 			rightshift = 0x01;
		// 			cnt = 0;
		// 		}

		// 	}
		// }

		
	}
}

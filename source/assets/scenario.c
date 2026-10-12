/* 由 tools/build_script.py 从 scenario/scenario.txt 自动生成，请勿手工修改。
 * 改剧情请改 scenario/scenario.txt 再重新生成。 */
#include "scenario.h"

static const char s_empty[] = "";
static const char s_3_s1[] = "魔女";
static const char s_3_s2[] = "海风停了。";
static const char s_5_s1[] = "魔女";
static const char s_5_s2[] = "你看，连浪都不肯再往前推了。";
static const char s_8_s1[] = "少女";
static const char s_8_s2[] = "……它又在叫我了。";
static const char s_10_s1[] = "魔女";
static const char s_10_s2[] = "叫你的东西，可不止那一座塔。";
static const char s_12_s2[] = "于是她们沿着海岸，走向那片黄色的沙。";
static const char s_15_s2[] = "那一天，沙漠里多了一个人的脚印。";
static const char s_16_s2[] = "序章 · 完";
static const char s_20_s2[] = "森林深处，有个东西一直站着没动。";
static const char s_21_s2[] = "它不是树。它在等。";
static const char s_23_s2[] = "天黑了。它还在。";
static const char s_25_s2[] = "第二幕 · 完";

const ScCmd scenario[] = {
    { CMD_BG, 0, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 2 */
    { CMD_BGM, 0, 1, 0, s_empty, s_empty, 0, 0 },   /* 行 3 */
    { CMD_CHAR, 0, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 4 */
    { CMD_SAY, 0, 0, 0, s_3_s1, s_3_s2, 0, 0 },   /* 行 5 */
    { CMD_VOICE, 1, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 6 */
    { CMD_SAY, 0, 0, 0, s_5_s1, s_5_s2, 0, 0 },   /* 行 7 */
    { CMD_VOICE, 2, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 8 */
    { CMD_CHAR, 2, 1, 0, s_empty, s_empty, 0, 0 },   /* 行 9 */
    { CMD_SAY, 0, 0, 0, s_8_s1, s_8_s2, 0, 0 },   /* 行 10 */
    { CMD_SE, 3, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 11 */
    { CMD_SAY, 0, 0, 0, s_10_s1, s_10_s2, 0, 0 },   /* 行 12 */
    { CMD_HIDE, 2, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 13 */
    { CMD_SAY, 0, 0, 0, s_empty, s_12_s2, 0, 0 },   /* 行 14 */
    { CMD_BG, 1, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 15 */
    { CMD_HIDE, 0, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 16 */
    { CMD_SAY, 0, 0, 0, s_empty, s_15_s2, 0, 0 },   /* 行 17 */
    { CMD_SAY, 0, 0, 0, s_empty, s_16_s2, 0, 0 },   /* 行 18 */
    { CMD_BG, 2, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 20 */
    { CMD_BGM, 0, 1, 0, s_empty, s_empty, 0, 0 },   /* 行 21 */
    { CMD_CHAR, 1, 2, 0, s_empty, s_empty, 0, 0 },   /* 行 22 */
    { CMD_SAY, 0, 0, 0, s_empty, s_20_s2, 0, 0 },   /* 行 23 */
    { CMD_SAY, 0, 0, 0, s_empty, s_21_s2, 0, 0 },   /* 行 24 */
    { CMD_BG, 3, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 25 */
    { CMD_SAY, 0, 0, 0, s_empty, s_23_s2, 0, 0 },   /* 行 26 */
    { CMD_HIDE, 1, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 27 */
    { CMD_SAY, 0, 0, 0, s_empty, s_25_s2, 0, 0 },   /* 行 28 */
    { CMD_END, 0, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 30 */
    { CMD_END, 0, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 0 */
};

const int scenario_count = 28;

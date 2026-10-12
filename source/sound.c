/* =====================================================================
 *  sound.c —— GBA 音频播放（Direct Sound A/B + DMA）
 *
 *  GBA 的声音硬件很省：
 *    · 只有 **2 路 PCM**（Direct Sound A / B），外加 2 路老式波形通道
 *    · 每路用一个定时器决定采样率（Timer0 → A，Timer1 → B）
 *    · PCM 数据靠 DMA 喂给 32 字节的 FIFO —— **DMA1/DMA2 专供声音**
 *      （本工程的图形用 DMA3，所以不冲突；这是当初选 DMA3 画图的原因之一）
 *
 *  本工程的用法：
 *    DS A → 语音（一次播完就停）
 *    DS B → BGM（循环）或 音效（音效会**抢占** B，播完把 BGM 放回去）
 *
 *  为什么要"抢占"而不是加一路：**硬件只有两路 PCM**。
 *  三个声音同时响（语音+BGM+音效）在这台机器上做不到，
 *  要么少一路，要么自己写软件混音（240x160 的机器上很奢侈）。
 *  这里选的做法是"音效优先"—— 音效短，抢占听感上最自然。
 *
 *  语音和 BGM 可以同时响（A 和 B 各一路），这是 galgame 最常见的组合。
 * ===================================================================== */
#include <tonc.h>

#include "sound.h"
#include "snd_data.h"

/* 采样率 → 定时器重载值。16.777216 MHz 是 GBA 的主频。 */
static u16 rate_to_tm(u32 rate)
{
    if (rate < 256) rate = 256;
    u32 v = 16777216u / rate;
    if (v < 1) v = 1;
    if (v > 0xFFFF) v = 0xFFFF;
    return (u16)v;
}

/* ---------------------------------------------------------------------
 * 状态
 * ------------------------------------------------------------------- */
static const SndClip *s_voice;      /* 正在播的语音（NULL = 没有） */
static u32 s_voice_left;            /* 还剩多少字节 */
static u32 s_voice_per_frame;       /* 每帧消耗多少字节（用于按帧推进） */

static const SndClip *s_bgm;        /* 当前 BGM */
static u32 s_bgm_pos;               /* BGM 播到第几字节（音效抢占后靠它恢复） */
static int s_bgm_playing;
static int s_bgm_loop;

static const SndClip *s_se;         /* 正在播的音效 */
static u32 s_se_left;

static int s_ready;

/* ---------------------------------------------------------------------
 * DS A / DS B 的启停
 * ------------------------------------------------------------------- */
static void ds_a_start(const SndClip *c, u32 offset)
{
    REG_SNDDSCNT &= ~(SDS_AR | SDS_AL);              /* 先关输出再改配置 */
    REG_DMA1CNT = 0;
    REG_SNDDSCNT |= SDS_ARESET;                      /* 清 FIFO，避免上一段的残留 */

    REG_TM0D = 0x10000 - rate_to_tm(c->rate);
    REG_TM0CNT = TM_ENABLE | TM_FREQ_1;

    REG_DMA1SAD = (u32)(c->data + offset);
    REG_DMA1DAD = (u32)&REG_FIFO_A;
    /* DMA_REPEAT：FIFO 每次要数据就自动再搬一轮（源地址自动重载），
     * 所以**不需要每采样中断** —— 这是 GBA 放 PCM 的标准写法。 */
    REG_DMA1CNT = DMA_ENABLE | DMA_REPEAT | DMA_32 | DMA_DST_FIXED;

    REG_SNDDSCNT |= SDS_A100 | SDS_AR | SDS_AL;      /* 100% 音量，左右都开 */
}

static void ds_a_stop(void)
{
    REG_SNDDSCNT &= ~(SDS_AR | SDS_AL);
    REG_DMA1CNT = 0;
    REG_TM0CNT = 0;
    REG_SNDDSCNT |= SDS_ARESET;
}

static void ds_b_start(const SndClip *c, u32 offset)
{
    REG_SNDDSCNT &= ~(SDS_BR | SDS_BL);
    REG_DMA2CNT = 0;
    REG_SNDDSCNT |= SDS_BRESET;

    REG_TM1D = 0x10000 - rate_to_tm(c->rate);
    REG_TM1CNT = TM_ENABLE | TM_FREQ_1;

    REG_DMA2SAD = (u32)(c->data + offset);
    REG_DMA2DAD = (u32)&REG_FIFO_B;
    REG_DMA2CNT = DMA_ENABLE | DMA_REPEAT | DMA_32 | DMA_DST_FIXED;

    REG_SNDDSCNT |= SDS_B100 | SDS_BR | SDS_BL;
}

static void ds_b_stop(void)
{
    REG_SNDDSCNT &= ~(SDS_BR | SDS_BL);
    REG_DMA2CNT = 0;
    REG_TM1CNT = 0;
    REG_SNDDSCNT |= SDS_BRESET;
}

/* ---------------------------------------------------------------------
 * 对外接口
 * ------------------------------------------------------------------- */
void snd_init(void)
{
    REG_SNDSTAT = SSTAT_ENABLE;          /* 总开关必须先开 */
    REG_SNDDSCNT = SDS_A100 | SDS_B100;
    REG_SNDBIAS = 0x0200;                /* 标准偏置，见 GBATEK */

    s_voice = 0;
    s_bgm = 0;
    s_se = 0;
    s_bgm_playing = 0;
    s_bgm_pos = 0;
    s_ready = 1;
}

void snd_play_voice(const SndClip *c)
{
    if (!s_ready || !c || !c->len) return;
    s_voice = c;
    s_voice_left = c->len;
    /* 每秒消耗 = rate 字节；本引擎按 60 帧/秒推进 */
    s_voice_per_frame = (c->rate + 59) / 60;
    ds_a_start(c, 0);
}

void snd_stop_voice(void)
{
    if (!s_ready) return;
    s_voice = 0;
    s_voice_left = 0;
    ds_a_stop();
}

int snd_voice_busy(void)
{
    return s_voice != 0;
}

void snd_play_bgm(const SndClip *c, int loop)
{
    if (!s_ready || !c || !c->len) return;
    if (s_se) ds_b_stop();               /* 音效正在响：直接换掉 */
    s_bgm = c;
    s_bgm_pos = 0;
    s_bgm_playing = 1;
    s_bgm_loop = loop;
    ds_b_start(c, 0);
}

void snd_stop_bgm(void)
{
    if (!s_ready) return;
    s_bgm = 0;
    s_bgm_playing = 0;
    if (!s_se) ds_b_stop();              /* 音效还在响就别打断它 */
}

void snd_play_se(const SndClip *c)
{
    if (!s_ready || !c || !c->len) return;
    s_se = c;
    s_se_left = c->len;
    ds_b_start(c, 0);                    /* 抢占 B */
}

void snd_update(void)
{
    if (!s_ready) return;

    /* --- DS A：语音按帧倒计时，播完就停 --- */
    if (s_voice) {
        if (s_voice_left > s_voice_per_frame)
            s_voice_left -= s_voice_per_frame;
        else
            snd_stop_voice();
    }

    /* --- DS B：音效优先 --- */
    if (s_se) {
        u32 per = (s_se->rate + 59) / 60;
        if (s_se_left > per) {
            s_se_left -= per;
        } else {
            s_se = 0;
            if (s_bgm && s_bgm_playing)
                ds_b_start(s_bgm, s_bgm_pos);    /* 音效结束，BGM 从原位置接上 */
            else
                ds_b_stop();
        }
    } else if (s_bgm && s_bgm_playing) {
        u32 per = (s_bgm->rate + 59) / 60;
        s_bgm_pos += per;
        if (s_bgm_pos >= s_bgm->len) {
            s_bgm_pos = 0;
            if (!s_bgm_loop) {
                s_bgm_playing = 0;
                ds_b_stop();
            }
            /* 循环时把 DMA 源地址拨回开头。
             * DMA 的源地址寄存器是"每轮传输后重载"的，所以运行中改它就等于定位 —— 
             * 不需要停掉重开，听感上是一个干净的循环点。 */
            else
                REG_DMA2SAD = (u32)s_bgm->data;
        }
    }
}

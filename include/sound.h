/* =====================================================================
 *  sound.h —— GBA 音频播放（Direct Sound A/B）
 *
 *  分工（硬件只有 2 路 PCM，所以必须分工）：
 *      DS A → 语音
 *      DS B → BGM，音效会临时抢占
 *  语音和 BGM 能同时响；音效响起时 BGM 让位，音效结束自动从原位置接上。
 * ===================================================================== */
#ifndef SOUND_H
#define SOUND_H

#include <tonc.h>

#include "snd_data.h"

void snd_init(void);

/* 语音（DS A）：一次播完自动停 */
void snd_play_voice(const SndClip *c);
void snd_stop_voice(void);
int  snd_voice_busy(void);          /* 台词可以设成"等语音播完" */

/* BGM（DS B）：loop=1 循环，0 播完即止 */
void snd_play_bgm(const SndClip *c, int loop);
void snd_stop_bgm(void);

/* 音效（抢占 DS B） */
void snd_play_se(const SndClip *c);

/* 每帧调用一次：推进播放进度、处理循环与音效恢复 */
void snd_update(void);

#endif /* SOUND_H */

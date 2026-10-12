/* 由 tools/make_project_audio.py 自动生成，请勿手工修改 */
#ifndef SND_DATA_H
#define SND_DATA_H

#include <tonc.h>

/* 一段音频：8 位有符号 PCM 裸数据。
 * loop 只是"这条素材的建议值"，实际循环与否由 CMD_BGM 的 b 字段决定。 */
typedef struct {
    const s8 *data;
    u32 len;
    u16 rate;
    u16 loop;
} SndClip;

extern const SndClip snd_clips[];
extern const int snd_clips_count;

extern const s8 snd_aud_0[];
extern const s8 snd_aud_1[];
extern const s8 snd_aud_2[];
extern const s8 snd_aud_3[];

#endif /* SND_DATA_H */

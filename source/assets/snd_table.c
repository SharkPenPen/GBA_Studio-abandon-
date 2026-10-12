/* 由 tools/make_project_audio.py 自动生成，请勿手工修改 */
#include "snd_data.h"

extern const s8 snd_aud_0[];
extern const s8 snd_aud_1[];
extern const s8 snd_aud_2[];
extern const s8 snd_aud_3[];

const SndClip snd_clips[] = {
    { snd_aud_0, 44100, 11025, 1 },   /* bgm 序曲 */
    { snd_aud_1, 14552, 11025, 0 },   /* voice witch_0101 */
    { snd_aud_2, 10473, 11025, 0 },   /* voice girl_0102 */
    { snd_aud_3, 1984, 11025, 0 },   /* se 叮 */
};
const int snd_clips_count = 4;

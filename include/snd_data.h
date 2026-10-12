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
extern const s8 snd_aud_4[];
extern const s8 snd_aud_5[];
extern const s8 snd_aud_6[];
extern const s8 snd_aud_7[];
extern const s8 snd_aud_8[];
extern const s8 snd_aud_9[];
extern const s8 snd_aud_10[];
extern const s8 snd_aud_11[];
extern const s8 snd_aud_12[];
extern const s8 snd_aud_13[];
extern const s8 snd_aud_14[];
extern const s8 snd_aud_15[];
extern const s8 snd_aud_16[];
extern const s8 snd_aud_17[];
extern const s8 snd_aud_18[];
extern const s8 snd_aud_19[];
extern const s8 snd_aud_20[];
extern const s8 snd_aud_21[];
extern const s8 snd_aud_22[];
extern const s8 snd_aud_23[];
extern const s8 snd_aud_24[];
extern const s8 snd_aud_25[];
extern const s8 snd_aud_26[];
extern const s8 snd_aud_27[];
extern const s8 snd_aud_28[];
extern const s8 snd_aud_29[];
extern const s8 snd_aud_30[];
extern const s8 snd_aud_31[];
extern const s8 snd_aud_32[];
extern const s8 snd_aud_33[];
extern const s8 snd_aud_34[];
extern const s8 snd_aud_35[];
extern const s8 snd_aud_36[];
extern const s8 snd_aud_37[];
extern const s8 snd_aud_38[];
extern const s8 snd_aud_39[];
extern const s8 snd_aud_40[];
extern const s8 snd_aud_41[];
extern const s8 snd_aud_42[];
extern const s8 snd_aud_43[];
extern const s8 snd_aud_44[];
extern const s8 snd_aud_45[];
extern const s8 snd_aud_46[];
extern const s8 snd_aud_47[];
extern const s8 snd_aud_48[];
extern const s8 snd_aud_49[];
extern const s8 snd_aud_50[];
extern const s8 snd_aud_51[];
extern const s8 snd_aud_52[];
extern const s8 snd_aud_53[];
extern const s8 snd_aud_54[];
extern const s8 snd_aud_55[];
extern const s8 snd_aud_56[];
extern const s8 snd_aud_57[];
extern const s8 snd_aud_58[];
extern const s8 snd_aud_59[];
extern const s8 snd_aud_60[];
extern const s8 snd_aud_61[];
extern const s8 snd_aud_62[];
extern const s8 snd_aud_63[];
extern const s8 snd_aud_64[];
extern const s8 snd_aud_65[];
extern const s8 snd_aud_66[];
extern const s8 snd_aud_67[];
extern const s8 snd_aud_68[];
extern const s8 snd_aud_69[];
extern const s8 snd_aud_70[];
extern const s8 snd_aud_71[];
extern const s8 snd_aud_72[];
extern const s8 snd_aud_73[];
extern const s8 snd_aud_74[];
extern const s8 snd_aud_75[];
extern const s8 snd_aud_76[];
extern const s8 snd_aud_77[];
extern const s8 snd_aud_78[];
extern const s8 snd_aud_79[];
extern const s8 snd_aud_80[];
extern const s8 snd_aud_81[];
extern const s8 snd_aud_82[];
extern const s8 snd_aud_83[];
extern const s8 snd_aud_84[];
extern const s8 snd_aud_85[];
extern const s8 snd_aud_86[];
extern const s8 snd_aud_87[];
extern const s8 snd_aud_88[];
extern const s8 snd_aud_89[];
extern const s8 snd_aud_90[];
extern const s8 snd_aud_91[];
extern const s8 snd_aud_92[];
extern const s8 snd_aud_93[];
extern const s8 snd_aud_94[];
extern const s8 snd_aud_95[];
extern const s8 snd_aud_96[];
extern const s8 snd_aud_97[];
extern const s8 snd_aud_98[];
extern const s8 snd_aud_99[];
extern const s8 snd_aud_100[];
extern const s8 snd_aud_101[];
extern const s8 snd_aud_102[];
extern const s8 snd_aud_103[];
extern const s8 snd_aud_104[];
extern const s8 snd_aud_105[];
extern const s8 snd_aud_106[];
extern const s8 snd_aud_107[];
extern const s8 snd_aud_108[];
extern const s8 snd_aud_109[];
extern const s8 snd_aud_110[];
extern const s8 snd_aud_111[];
extern const s8 snd_aud_112[];

#endif /* SND_DATA_H */

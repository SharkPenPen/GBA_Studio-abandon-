/* 由 tools/build_script.py 从 scenario/scenario.txt 自动生成，请勿手工修改。
 * 改剧情请改 scenario/scenario.txt 再重新生成。 */
#include "scenario.h"

static const char s_empty[] = "";
static const char s_1_s2[] = "除灵结束，我和姐姐一起泡澡。";
static const char s_2_s2[] = "浴缸里注满热水，浸到脖子。 这是简直活到现在最舒服的瞬间。";
static const char s_4_s2[] = "甚至让我觉得…… 世上没有比这更舒服的事了。";
static const char s_5_s2[] = "但是…… 一个人泡澡，就没这么舒服了。";
static const char s_6_s2[] = "一定是…… 因为和姐姐在一起。";
static const char s_8_s1[] = "刹那";
static const char s_8_s2[] = "呼……真舒服……";
static const char s_10_s1[] = "悠果";
static const char s_10_s2[] = "呵呵……一脸幸福的表情…… 刹那是真的喜欢泡澡啊";
static const char s_12_s1[] = "刹那";
static const char s_12_s2[] = "诶？姐姐，讨厌吗？";
static const char s_14_s1[] = "悠果";
static const char s_14_s2[] = "怎么会，我超喜欢哦。 喜欢到会想…… 世上怎么会有人讨厌泡澡呢";
static const char s_16_s1[] = "悠果";
static const char s_16_s2[] = "而且，能像这样见证刹那的成长 也很高兴啊";
static const char s_19_s1[] = "刹那";
static const char s_19_s2[] = "姐姐，讨厌…… 你在说什么呀，真是的…… 好害羞恥的……";
static const char s_21_s1[] = "悠果";
static const char s_21_s2[] = "胸部也，不知不觉间， 成长到这么大";
static const char s_23_s1[] = "刹那";
static const char s_23_s2[] = "唔……要说胸部的大小， 姐姐不是比我要大多了吗";
static const char s_25_s1[] = "悠果";
static const char s_25_s2[] = "刹那也没输啊。 在班里的女生中算大了吧？";
static const char s_28_s1[] = "刹那";
static const char s_28_s2[] = "诶……？ 算大吗……没在意过诶。 又没和大家比过";
static const char s_30_s1[] = "悠果";
static const char s_30_s2[] = "你小时候身子小 当时还担心你会不会健康成长";
static const char s_33_s1[] = "刹那";
static const char s_33_s2[] = "诶？以前你这么担心我吗？ 完全看不出来啊……";
static const char s_35_s1[] = "悠果";
static const char s_35_s2[] = "哎呀……我是那么无情的姐姐吗？";
static const char s_37_s1[] = "刹那";
static const char s_37_s2[] = "倒不是这么说……姐姐以前 经常照顾孤儿院的其他孩子…… 还以为不要我了";
static const char s_40_s1[] = "悠果";
static const char s_40_s2[] = "那是……我不能 一直跟着刹那呀…… 还有很多无依无靠的孩子";
static const char s_42_s1[] = "悠果";
static const char s_42_s2[] = "我们两姐妹一起被领养， 还算是幸福的啊";
static const char s_45_s1[] = "刹那";
static const char s_45_s2[] = "嗯，现在我也能理解， 那时候的我觉得是， 姐姐被人抢走了";
static const char s_47_s1[] = "悠果";
static const char s_47_s2[] = "刹那……";
static const char s_49_s1[] = "刹那";
static const char s_49_s2[] = "我一直以为 姐姐是属于我一个人的";
static const char s_51_s2[] = "感觉自己在说很羞耻的话…… 但是偶然说，也可以吧。";
static const char s_53_s1[] = "悠果";
static const char s_53_s2[] = "呵呵……那时候的刹那， 一直缠着我的手臂不放呢";
static const char s_55_s1[] = "刹那";
static const char s_55_s2[] = "因为……那时候的我的世界里， 真的只有姐姐啊";
static const char s_57_s2[] = "现在，还有青梅竹马的冬马， 养育我们的神父大人， 也多了很多朋友。";
static const char s_58_s2[] = "世界变得更加宽广，但即便如此 姐姐是我唯一的，特别的亲人，这一点一直没变。";
static const char s_60_s1[] = "刹那";
static const char s_60_s2[] = "关于母亲也…… 只知道神父大人口中的故事……";
static const char s_62_s1[] = "悠果";
static const char s_62_s2[] = "毕竟只告诉我们…… 是因事故去世的。 连照片都没有留下";
static const char s_64_s1[] = "刹那";
static const char s_64_s2[] = "关于父亲更是， 完全不了解……";
static const char s_66_s1[] = "悠果";
static const char s_66_s2[] = "听说在母亲依靠着教会的时期 只带了我们两个过来……";
static const char s_68_s1[] = "悠果";
static const char s_68_s2[] = "关于父亲母亲什么都没有说 说不定是因为 有过痛苦的遭遇";
static const char s_71_s2[] = "说不定，受到了暴力对待…… 也是有可能的。";
static const char s_72_s2[] = "但那也只是想象， 知晓事实几乎已不可能。";
static const char s_73_s2[] = "我们对双亲的了解 实在是太少了……。";
static const char s_74_s2[] = "其他知道的只有， 母亲曾经是伏魔师…… 而且非常优秀……。";
static const char s_75_s2[] = "神父大人说母亲去世是因为交通事故 因为不了解详细情况，所以没有向我们解释。";
static const char s_76_s2[] = "我们自己去调查的话，说不定能知道些什么……。";
static const char s_77_s2[] = "继续这样什么都不知道就好吗……？ 内心似乎在如此诉说。";
static const char s_79_s1[] = "悠果";
static const char s_79_s2[] = "我说刹那，最近，你觉得怎么样？";
static const char s_81_s1[] = "刹那";
static const char s_81_s2[] = "……明显，变多了啊";
static const char s_83_s1[] = "刹那";
static const char s_83_s2[] = "我虽然还没做过很久， 但这么频繁的情况，是第一次遇到";
static const char s_85_s1[] = "悠果";
static const char s_85_s2[] = "从别的地区的伏魔师那听说 每隔几年就会这样来一次。 我也是第一次遇到这种事……";
static const char s_87_s1[] = "刹那";
static const char s_87_s2[] = "不由得会去想…… 是不是不祥之事发生的前兆呢……";
static const char s_89_s1[] = "悠果";
static const char s_89_s2[] = "嗯，是啊……。 虽然不想这么考虑…… 总觉得，心里有块疙瘩……";
static const char s_91_s1[] = "刹那";
static const char s_91_s2[] = "神父大人是怎么想的呢？";
static const char s_93_s1[] = "悠果";
static const char s_93_s2[] = "什么都没说 但看起来忧心忡忡……";
static const char s_95_s1[] = "刹那";
static const char s_95_s2[] = "他知道些什么吗？ 关于这次的事……";
static const char s_97_s1[] = "悠果";
static const char s_97_s2[] = "不知道啊…… 如果认为有必要的话应该会告诉我们";
static const char s_99_s1[] = "刹那";
static const char s_99_s2[] = "刚才说每隔几年会发生一次 理由是什么呢？";
static const char s_101_s1[] = "悠果";
static const char s_101_s2[] = "这人家也不知道……";
static const char s_103_s1[] = "刹那";
static const char s_103_s2[] = "也是哦……这和恶魔附身者 出现的理由也差不多吧";
static const char s_105_s2[] = "在伏魔师之间一直被讨论的话题。 谁也不知道答案……。";
static const char s_107_s1[] = "悠果";
static const char s_107_s2[] = "啊……对了对了。 说好要给刹那擦背的";
static const char s_109_s2[] = "气氛开始变得低迷之际， 姐姐突然装傻般说道。";
static const char s_110_s2[] = "不知是为了改善沉重的氛围， 还是真的现在才想起来……。";
static const char s_111_s2[] = "姐姐的话，都有可能吧。";
static const char s_112_s2[] = "但是，我也不再追问，直接接上姐姐的话题。";
static const char s_114_s1[] = "刹那";
static const char s_114_s2[] = "是啊。 姐姐你忘了吧？";
static const char s_116_s1[] = "悠果";
static const char s_116_s2[] = "哎呀哎呀。我可没忘哦？ 来，背朝我";
static const char s_118_s1[] = "刹那";
static const char s_118_s2[] = "好~。 那就拜托了";
static const char s_120_s2[] = "姐姐开始用海绵给我擦背。 沐浴露的泡沫温柔地裹住我的后背。";
static const char s_122_s2[] = "力道和触感都非常舒服。 真希望能一直这样下去。";
static const char s_123_s2[] = "只有在一起洗澡的时候 才是不被任何人打扰的二人世界……";
static const char s_124_s2[] = "这是能够独占姐姐的我的特权。";
static const char s_125_s2[] = "然后是我给姐姐擦背。 只有我能摸到姐姐光滑白皙的肌肤。";
static const char s_127_s2[] = "姐姐是属于我一个人的……";
static const char s_128_s2[] = "或许终有一天 姐姐将不属于我。";
static const char s_129_s2[] = "但现在不必在意…… 我发自内心地希望如此……。";
static const char s_131_s1[] = "刹那";
static const char s_131_s2[] = "呼……好舒服啊。 除灵之后泡的澡最爽了";
static const char s_133_s2[] = "洗完澡后只穿着内衣 我和姐姐让身体降降温。";
static const char s_134_s2[] = "虽说有些不成体统， 但现在只有我们姐妹俩，稍微放松一下 不也挺好的吗……？";
static const char s_135_s1[] = "悠果";
static const char s_135_s2[] = "毕竟出了一身汗呢。";
static const char s_137_s1[] = "刹那";
static const char s_137_s2[] = "除了出汗以外， 还有恶魔的气味，潮湿的空气，呕吐物， 感觉还粘上了各种东西……";
static const char s_139_s1[] = "刹那";
static const char s_139_s2[] = "普通的生活中绝对没有的东西 把这些都冲洗干净，真的好爽啊";
static const char s_141_s1[] = "悠果";
static const char s_141_s2[] = "是啊…… 恶魔附身者的房间里有各种……";
static const char s_143_s2[] = "姐姐这么说着向我微笑。 我们平凡的日常又回来了。";
static const char s_144_s2[] = "刚才还在和恶魔战斗…… 这种事都忘掉……";
static const char s_146_s1[] = "刹那";
static const char s_146_s2[] = "刚刚救下的女孩子…… 没有事吧";
static const char s_148_s2[] = "姐姐的表情略显黯淡。";
static const char s_149_s2[] = "虽然附身的恶魔驱走了， 但还是留下了皮肤破裂等外表上的影响 这一点令人在意。";
static const char s_150_s1[] = "悠果";
static const char s_150_s2[] = "被那么强大的恶魔附身， 无论如何都会产生强烈的影响…… 恢复到原样可要花点时间啊……";
static const char s_152_s1[] = "悠果";
static const char s_152_s2[] = "被恶魔附身时的记忆应该是没有的， 所以可能不知道为什么会变成那样……";
static const char s_154_s1[] = "刹那";
static const char s_154_s2[] = "毕竟是女孩子。 肯定会受到打击吧……";
static const char s_156_s1[] = "悠果";
static const char s_156_s2[] = "是啊……我们去帮她 克服心理阴影吧？";
static const char s_158_s1[] = "刹那";
static const char s_158_s2[] = "嗯……大概会一段时间不能上学， 我们要让她振作起来";
static const char s_160_s1[] = "悠果";
static const char s_160_s2[] = "我打算早上，去教会之前去看一下情况。 刹那就放学顺路去看一下？";
static const char s_162_s1[] = "刹那";
static const char s_162_s2[] = "嗯。好。 要不要带点能让人打起精神的东西呢";
static const char s_164_s1[] = "悠果";
static const char s_164_s2[] = "带点甜食，或许不错哦。 而且实际上，她也应该消耗了不少能量";
static const char s_166_s1[] = "刹那";
static const char s_166_s2[] = "那就，去车站的点心店去买点吃的";
static const char s_169_s2[] = "我这么回答， 姐姐绽开了笑容。";
static const char s_170_s1[] = "刹那";
static const char s_170_s2[] = "怎么了，姐姐？ 看起来很开心啊";
static const char s_172_s1[] = "悠果";
static const char s_172_s2[] = "想到刹那也渐渐像个修女 变得有模有样了";
static const char s_174_s1[] = "刹那";
static const char s_174_s2[] = "诶~，什么嘛。 我就是修女啊？ 不过，现在是学业优先……";
static const char s_176_s1[] = "悠果";
static const char s_176_s2[] = "我们修女，只要有人在苦恼 就要代替神明向他们伸出援助之手。 这份心意非常重要……";
static const char s_178_s1[] = "悠果";
static const char s_178_s2[] = "母亲一定，也觉得高兴的";
static const char s_181_s2[] = "姐姐这么说着再次微笑。 但是……表情却有些寂寞。";
static const char s_182_s2[] = "要是母亲还活着…… 我们现在会怎么样呢……。";
static const char s_183_s2[] = "没有成为伏魔师 过着普通女孩子生活吗……";
static const char s_184_s2[] = "但是……考虑这种事情也毫无意义。";
static const char s_185_s2[] = "我和姐姐必须互相保护一起活下去。 我们是二位一体。";
static const char s_186_s2[] = "不管怎么样，今天的除灵结束了 不要多想，好好睡一觉吧……。";
static const char s_188_s1[] = "刹那";
static const char s_188_s2[] = "那，我差不多该睡了。 晚安，姐姐。 明天见";
static const char s_190_s1[] = "悠果";
static const char s_190_s2[] = "嗯。 晚安，刹那……";
static const char s_192_s2[] = "我们互相微笑，走向了各自的房间。";
static const char s_194_s2[] = "──数日后。";
static const char s_195_s2[] = "上午的课程结束，到了午餐时间。 无论怎么说，都是学校最热闹的时间。";
static const char s_197_s2[] = "大家愉快地往桌上摆出便当。 但是，今天我……。";
static const char s_198_s1[] = "冬馬";
static const char s_198_s2[] = "刹那，今天没拿便当吗？";
static const char s_199_s1[] = "刹那";
static const char s_199_s2[] = "今天早上，稍微起晚了……";
static const char s_201_s1[] = "冬馬";
static const char s_201_s2[] = "真少见啊，刹那早上竟然起晚了";
static const char s_202_s1[] = "刹那";
static const char s_202_s2[] = "因为昨天的除灵，一直持续到深夜……。 实在是起不来";
static const char s_204_s1[] = "冬馬";
static const char s_204_s2[] = "悠果怎么样？";
static const char s_205_s1[] = "刹那";
static const char s_205_s2[] = "说是早上要准备教会的活动， 直接睡在教会了。大概姐姐也 没有自信能早起吧";
static const char s_207_s1[] = "冬馬";
static const char s_207_s2[] = "很辛苦嘛…… 要不然我的便当，分你一半？";
static const char s_208_s1[] = "刹那";
static const char s_208_s2[] = "不用。没事的。 我去小卖部买个面包吃。 好意心领了，谢谢……嗯？";
static const char s_210_s2[] = "突然手机开始震动。 一看画面是神父大人打来的。也就是说……";
static const char s_212_s2[] = "我急忙躲到教室的角落接通电话。";
static const char s_214_s1[] = "刹那";
static const char s_214_s2[] = "喂你好……";
static const char s_216_s1[] = "神父";
static const char s_216_s2[] = "……刹那吗，抱歉啊。 其实又有一份委托，是今晚的， 没问题吗？";
static const char s_217_s1[] = "刹那";
static const char s_217_s2[] = "好的。没问题";
static const char s_219_s1[] = "神父";
static const char s_219_s2[] = "……是吗。 那就拜托你了，再见";
static const char s_220_s2[] = "神父大人挂断了电话。";
static const char s_221_s2[] = "我想起了之前冬马说过的话。 最近恶魔附身者的委托多了起来……";
static const char s_222_s1[] = "冬馬";
static const char s_222_s2[] = "教会的电话？";
static const char s_223_s1[] = "刹那";
static const char s_223_s2[] = "嗯……。 我说冬马。你还记得吗？之前对我说的话";
static const char s_225_s1[] = "冬馬";
static const char s_225_s2[] = "记得啊。果然在变多了啊……";
static const char s_226_s1[] = "刹那";
static const char s_226_s2[] = "连续两天，我是第一次遇到";
static const char s_228_s1[] = "冬馬";
static const char s_228_s2[] = "其他地方也是这样吗？ 还是说，只有这附近？";
static const char s_229_s1[] = "刹那";
static const char s_229_s2[] = "据我所知，似乎只有这一带。 每隔几年，会发生这样的事， 但是好像也没什么规律";
static const char s_231_s1[] = "冬馬";
static const char s_231_s2[] = "这样啊。 希望不是什么坏事 发生的前兆就好……";
static const char s_232_s1[] = "刹那";
static const char s_232_s2[] = "…………";
static const char s_234_s2[] = "冬马的想法和我完全相同， 我不由自主默默地看着他。";
static const char s_235_s1[] = "冬馬";
static const char s_235_s2[] = "……怎么了？";
static const char s_236_s1[] = "刹那";
static const char s_236_s2[] = "没，没什么。什么都没有。 是啊……哦，我去小卖部 买午饭了";
static const char s_238_s1[] = "冬馬";
static const char s_238_s2[] = "啊，嗯。路上小心";
static const char s_239_s2[] = "也不是很想聊的内容， 我结束了话题走向了小卖部。";
static const char s_241_s2[] = "虽然自觉不雅， 但我还是以接近奔跑的速度走向小卖部。";
static const char s_243_s2[] = "说实话，没有馅的小面包， 是真的不想当午餐。";
static const char s_244_s2[] = "这么想着，正好走下楼梯的瞬间， 突然间背后被人推了一把。";
static const char s_245_s1[] = "刹那";
static const char s_245_s2[] = "诶……！？咕……！";
static const char s_247_s2[] = "快要从楼梯上掉下去的瞬间， 我匆忙中奋力一跃，在空中回转身体。";
static const char s_248_s2[] = "然后，总算是成功着地。";
static const char s_250_s1[] = "刹那";
static const char s_250_s2[] = "谁……？诶……！？";
static const char s_252_s1[] = "女子学生";
static const char s_252_s2[] = "呀啊啊啊啊！？";
static const char s_253_s2[] = "我正想确认是谁推了我，向上看的瞬间， 一个女孩子从楼梯上掉了下来。";
static const char s_254_s1[] = "刹那";
static const char s_254_s2[] = "危险！";
static const char s_256_s2[] = "这样下去会重重摔到地上……。 我一想到这，赶紧接住了女孩子。";
static const char s_258_s2[] = "…………。";
static const char s_259_s2[] = "结果，我现在一边啃着没有馅的面包， 一边喝着牛奶。";
static const char s_260_s2[] = "左脚踝去医务室接受了简单的治疗 上面绑着绷带。";
static const char s_261_s1[] = "冬馬";
static const char s_261_s2[] = "真是灾难啊";
static const char s_262_s1[] = "刹那";
static const char s_262_s2[] = "嘛……还好掉下来的女孩子没有受伤。 我也只是轻微扭伤";
static const char s_264_s2[] = "推我下楼的人，和女孩子从楼梯上 掉下来的原因都不知道，这一点令人毛骨悚然， 不过好在是没有酿成大祸。";
static const char s_265_s1[] = "冬馬";
static const char s_265_s2[] = "不过，你这脚，今天的除灵是不行了吧";
static const char s_266_s2[] = "确实冬马说得没错。 以非万全的状态去挑战敌人非常危险。";
static const char s_267_s1[] = "刹那";
static const char s_267_s2[] = "嗯……虽然也要看对手是谁……说的也是， 我去联络姐姐一下";
static const char s_269_s2[] = "离开座位到角落向姐姐打电话。 马上就接通了。";
static const char s_271_s1[] = "悠果";
static const char s_271_s2[] = "……刹那？怎么了？";
static const char s_273_s1[] = "刹那";
static const char s_273_s2[] = "姐姐，那个……其实…… 我，稍微受了点伤……";
static const char s_275_s1[] = "悠果";
static const char s_275_s2[] = "受伤！？没，没事吧？";
static const char s_277_s1[] = "刹那";
static const char s_277_s2[] = "嗯，不是很严重的伤， 脚踝扭了……";
static const char s_279_s2[] = "从楼梯上掉了下去，这我说不出口。 不能让姐姐太担心我。";
static const char s_280_s1[] = "刹那";
static const char s_280_s2[] = "然后，刚才神父大人打电话来了。 说是有除灵的委托";
static const char s_282_s1[] = "悠果";
static const char s_282_s2[] = "嗯……是啊";
static const char s_284_s1[] = "刹那";
static const char s_284_s2[] = "然后呢，想先问问是怎么样的对手， 冬马说如果自己 能帮忙就会去……";
static const char s_286_s1[] = "悠果";
static const char s_286_s2[] = "……冬马不行的啦。 这次也是恶魔附身的委托";
static const char s_288_s2[] = "冬马没有驱除附身恶魔的能力。 只有在物理上战斗的时候能帮上忙。";
static const char s_289_s1[] = "刹那";
static const char s_289_s2[] = "那，果然还是得我去啊。 放学后我过来吧";
static const char s_291_s1[] = "悠果";
static const char s_291_s2[] = "不了，这次的委托我一个人也没问题。 其实，现在还不清楚 到底是不是恶魔附身";
static const char s_293_s1[] = "悠果";
static const char s_293_s2[] = "所以，首要目的是去确认情况。 神父大人也真爱担心";
static const char s_295_s1[] = "刹那";
static const char s_295_s2[] = "啊，姐姐……。 果然，恶魔附身的委托在变多吧？ 我有不祥的预感……";
static const char s_297_s1[] = "悠果";
static const char s_297_s2[] = "嗯……";
static const char s_299_s1[] = "刹那";
static const char s_299_s2[] = "我还是去吧。 尽量不碍事";
static const char s_301_s1[] = "悠果";
static const char s_301_s2[] = "没事的。要是觉得危险 我会回去一趟做好充分准备的。 所以刹那你就做好晚饭等我回来吧";
static const char s_303_s1[] = "刹那";
static const char s_303_s2[] = "我知道了……嗯。 对不起哦，姐姐。小心哦";
static const char s_305_s1[] = "悠果";
static const char s_305_s2[] = "谢谢。 啊，对了对了，即使是扭伤， 恶化了也会拖很久才会好，要小心哦。再见";
static const char s_307_s2[] = "姐姐挂断了电话。";
static const char s_308_s2[] = "说实话我有点松了一口气。";
static const char s_309_s2[] = "只是调查是不是恶魔附身的话 我不在也，没事的吧……。";
static const char s_310_s1[] = "冬馬";
static const char s_310_s2[] = "悠果怎么说？";
static const char s_311_s1[] = "刹那";
static const char s_311_s2[] = "说是今天的委托一个人也没问题。 我就回家做好晚饭等她回来";
static const char s_313_s1[] = "冬馬";
static const char s_313_s2[] = "我也来帮忙吧？";
static const char s_314_s1[] = "刹那";
static const char s_314_s2[] = "诶？才不要，冬马会做的 不是只有泡面吗？";
static const char s_316_s1[] = "刹那";
static const char s_316_s2[] = "我也会用菜刀的，没问题。 我也想给工作疲惫而归的姐姐 做点正常的料理";
static const char s_318_s1[] = "冬馬";
static const char s_318_s2[] = "就算这么说，刹那不也 只会做炸鸡嘛";
static const char s_319_s1[] = "刹那";
static const char s_319_s2[] = "炸鸡也是正常的料理啊。 而且姐姐，很喜欢 吃我做的炸鸡啊";
static const char s_322_s2[] = "和冬马日常聊天的同事 我的心中感到了一丝不安。";
static const char s_323_s2[] = "让姐姐一个人去没问题吗…… 想起了之前驱除的恶魔的话语……";
static const char s_324_s2[] = "你们是属于我们的……";
static const char s_325_s2[] = "心中的不祥预感没有消失……";
static const char s_326_s1[] = "父親";
static const char s_326_s2[] = "来的正是时候…… 非常感谢……";
static const char s_327_s1[] = "悠果";
static const char s_327_s2[] = "您是委托人父亲吗？";
static const char s_329_s1[] = "父親";
static const char s_329_s2[] = "是的没错…… 是我向神父大人委托的……";
static const char s_330_s2[] = "父亲说话时始终表情虚无 目光无神。";
static const char s_331_s1[] = "悠果";
static const char s_331_s2[] = "那么，令郎现在在哪里呢？";
static const char s_333_s1[] = "父親";
static const char s_333_s2[] = "压制住以后关在地下室…… 因为他一边口吐污言一边破坏房间……";
static const char s_334_s1[] = "悠果";
static const char s_334_s2[] = "为什么会怀疑令郎 被恶魔附身呢";

const ScCmd scenario[] = {
    { CMD_BG, 0, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 2 */
    { CMD_SAY, 0, 0, 0, s_empty, s_1_s2, 0, 0 },   /* 行 3 */
    { CMD_SAY, 0, 0, 0, s_empty, s_2_s2, 0, 0 },   /* 行 4 */
    { CMD_VOICE, 0, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 5 */
    { CMD_SAY, 0, 0, 0, s_empty, s_4_s2, 0, 0 },   /* 行 6 */
    { CMD_SAY, 0, 0, 0, s_empty, s_5_s2, 0, 0 },   /* 行 7 */
    { CMD_SAY, 0, 0, 0, s_empty, s_6_s2, 0, 0 },   /* 行 8 */
    { CMD_BG, 1, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 9 */
    { CMD_SAY, 0, 0, 0, s_8_s1, s_8_s2, 0, 0 },   /* 行 10 */
    { CMD_VOICE, 1, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 11 */
    { CMD_SAY, 0, 0, 0, s_10_s1, s_10_s2, 0, 0 },   /* 行 12 */
    { CMD_VOICE, 2, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 13 */
    { CMD_SAY, 0, 0, 0, s_12_s1, s_12_s2, 0, 0 },   /* 行 14 */
    { CMD_VOICE, 3, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 15 */
    { CMD_SAY, 0, 0, 0, s_14_s1, s_14_s2, 0, 0 },   /* 行 16 */
    { CMD_VOICE, 4, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 17 */
    { CMD_SAY, 0, 0, 0, s_16_s1, s_16_s2, 0, 0 },   /* 行 18 */
    { CMD_VOICE, 5, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 19 */
    { CMD_BG, 2, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 20 */
    { CMD_SAY, 0, 0, 0, s_19_s1, s_19_s2, 0, 0 },   /* 行 21 */
    { CMD_VOICE, 6, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 22 */
    { CMD_SAY, 0, 0, 0, s_21_s1, s_21_s2, 0, 0 },   /* 行 23 */
    { CMD_VOICE, 7, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 24 */
    { CMD_SAY, 0, 0, 0, s_23_s1, s_23_s2, 0, 0 },   /* 行 25 */
    { CMD_VOICE, 8, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 26 */
    { CMD_SAY, 0, 0, 0, s_25_s1, s_25_s2, 0, 0 },   /* 行 27 */
    { CMD_VOICE, 9, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 28 */
    { CMD_BG, 3, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 29 */
    { CMD_SAY, 0, 0, 0, s_28_s1, s_28_s2, 0, 0 },   /* 行 30 */
    { CMD_VOICE, 10, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 31 */
    { CMD_SAY, 0, 0, 0, s_30_s1, s_30_s2, 0, 0 },   /* 行 32 */
    { CMD_VOICE, 11, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 33 */
    { CMD_BG, 4, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 34 */
    { CMD_SAY, 0, 0, 0, s_33_s1, s_33_s2, 0, 0 },   /* 行 35 */
    { CMD_VOICE, 12, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 36 */
    { CMD_SAY, 0, 0, 0, s_35_s1, s_35_s2, 0, 0 },   /* 行 37 */
    { CMD_VOICE, 13, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 38 */
    { CMD_SAY, 0, 0, 0, s_37_s1, s_37_s2, 0, 0 },   /* 行 39 */
    { CMD_VOICE, 14, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 40 */
    { CMD_BG, 5, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 41 */
    { CMD_SAY, 0, 0, 0, s_40_s1, s_40_s2, 0, 0 },   /* 行 42 */
    { CMD_VOICE, 15, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 43 */
    { CMD_SAY, 0, 0, 0, s_42_s1, s_42_s2, 0, 0 },   /* 行 44 */
    { CMD_VOICE, 16, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 45 */
    { CMD_BG, 6, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 46 */
    { CMD_SAY, 0, 0, 0, s_45_s1, s_45_s2, 0, 0 },   /* 行 47 */
    { CMD_VOICE, 17, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 48 */
    { CMD_SAY, 0, 0, 0, s_47_s1, s_47_s2, 0, 0 },   /* 行 49 */
    { CMD_VOICE, 18, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 50 */
    { CMD_SAY, 0, 0, 0, s_49_s1, s_49_s2, 0, 0 },   /* 行 51 */
    { CMD_VOICE, 19, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 52 */
    { CMD_SAY, 0, 0, 0, s_empty, s_51_s2, 0, 0 },   /* 行 53 */
    { CMD_BG, 7, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 54 */
    { CMD_SAY, 0, 0, 0, s_53_s1, s_53_s2, 0, 0 },   /* 行 55 */
    { CMD_VOICE, 20, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 56 */
    { CMD_SAY, 0, 0, 0, s_55_s1, s_55_s2, 0, 0 },   /* 行 57 */
    { CMD_VOICE, 21, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 58 */
    { CMD_SAY, 0, 0, 0, s_empty, s_57_s2, 0, 0 },   /* 行 59 */
    { CMD_SAY, 0, 0, 0, s_empty, s_58_s2, 0, 0 },   /* 行 60 */
    { CMD_BG, 6, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 61 */
    { CMD_SAY, 0, 0, 0, s_60_s1, s_60_s2, 0, 0 },   /* 行 62 */
    { CMD_VOICE, 22, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 63 */
    { CMD_SAY, 0, 0, 0, s_62_s1, s_62_s2, 0, 0 },   /* 行 64 */
    { CMD_VOICE, 23, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 65 */
    { CMD_SAY, 0, 0, 0, s_64_s1, s_64_s2, 0, 0 },   /* 行 66 */
    { CMD_VOICE, 24, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 67 */
    { CMD_SAY, 0, 0, 0, s_66_s1, s_66_s2, 0, 0 },   /* 行 68 */
    { CMD_VOICE, 25, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 69 */
    { CMD_SAY, 0, 0, 0, s_68_s1, s_68_s2, 0, 0 },   /* 行 70 */
    { CMD_VOICE, 26, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 71 */
    { CMD_BG, 8, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 72 */
    { CMD_SAY, 0, 0, 0, s_empty, s_71_s2, 0, 0 },   /* 行 73 */
    { CMD_SAY, 0, 0, 0, s_empty, s_72_s2, 0, 0 },   /* 行 74 */
    { CMD_SAY, 0, 0, 0, s_empty, s_73_s2, 0, 0 },   /* 行 75 */
    { CMD_SAY, 0, 0, 0, s_empty, s_74_s2, 0, 0 },   /* 行 76 */
    { CMD_SAY, 0, 0, 0, s_empty, s_75_s2, 0, 0 },   /* 行 77 */
    { CMD_SAY, 0, 0, 0, s_empty, s_76_s2, 0, 0 },   /* 行 78 */
    { CMD_SAY, 0, 0, 0, s_empty, s_77_s2, 0, 0 },   /* 行 79 */
    { CMD_BG, 9, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 80 */
    { CMD_SAY, 0, 0, 0, s_79_s1, s_79_s2, 0, 0 },   /* 行 81 */
    { CMD_VOICE, 27, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 82 */
    { CMD_SAY, 0, 0, 0, s_81_s1, s_81_s2, 0, 0 },   /* 行 83 */
    { CMD_VOICE, 28, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 84 */
    { CMD_SAY, 0, 0, 0, s_83_s1, s_83_s2, 0, 0 },   /* 行 85 */
    { CMD_VOICE, 29, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 86 */
    { CMD_SAY, 0, 0, 0, s_85_s1, s_85_s2, 0, 0 },   /* 行 87 */
    { CMD_VOICE, 30, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 88 */
    { CMD_SAY, 0, 0, 0, s_87_s1, s_87_s2, 0, 0 },   /* 行 89 */
    { CMD_VOICE, 31, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 90 */
    { CMD_SAY, 0, 0, 0, s_89_s1, s_89_s2, 0, 0 },   /* 行 91 */
    { CMD_VOICE, 32, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 92 */
    { CMD_SAY, 0, 0, 0, s_91_s1, s_91_s2, 0, 0 },   /* 行 93 */
    { CMD_VOICE, 33, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 94 */
    { CMD_SAY, 0, 0, 0, s_93_s1, s_93_s2, 0, 0 },   /* 行 95 */
    { CMD_VOICE, 34, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 96 */
    { CMD_SAY, 0, 0, 0, s_95_s1, s_95_s2, 0, 0 },   /* 行 97 */
    { CMD_VOICE, 35, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 98 */
    { CMD_SAY, 0, 0, 0, s_97_s1, s_97_s2, 0, 0 },   /* 行 99 */
    { CMD_VOICE, 36, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 100 */
    { CMD_SAY, 0, 0, 0, s_99_s1, s_99_s2, 0, 0 },   /* 行 101 */
    { CMD_VOICE, 37, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 102 */
    { CMD_SAY, 0, 0, 0, s_101_s1, s_101_s2, 0, 0 },   /* 行 103 */
    { CMD_VOICE, 38, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 104 */
    { CMD_SAY, 0, 0, 0, s_103_s1, s_103_s2, 0, 0 },   /* 行 105 */
    { CMD_VOICE, 39, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 106 */
    { CMD_SAY, 0, 0, 0, s_empty, s_105_s2, 0, 0 },   /* 行 107 */
    { CMD_BG, 10, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 108 */
    { CMD_SAY, 0, 0, 0, s_107_s1, s_107_s2, 0, 0 },   /* 行 109 */
    { CMD_VOICE, 40, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 110 */
    { CMD_SAY, 0, 0, 0, s_empty, s_109_s2, 0, 0 },   /* 行 111 */
    { CMD_SAY, 0, 0, 0, s_empty, s_110_s2, 0, 0 },   /* 行 112 */
    { CMD_SAY, 0, 0, 0, s_empty, s_111_s2, 0, 0 },   /* 行 113 */
    { CMD_SAY, 0, 0, 0, s_empty, s_112_s2, 0, 0 },   /* 行 114 */
    { CMD_BG, 11, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 115 */
    { CMD_SAY, 0, 0, 0, s_114_s1, s_114_s2, 0, 0 },   /* 行 116 */
    { CMD_VOICE, 41, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 117 */
    { CMD_SAY, 0, 0, 0, s_116_s1, s_116_s2, 0, 0 },   /* 行 118 */
    { CMD_VOICE, 42, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 119 */
    { CMD_SAY, 0, 0, 0, s_118_s1, s_118_s2, 0, 0 },   /* 行 120 */
    { CMD_VOICE, 43, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 121 */
    { CMD_SAY, 0, 0, 0, s_empty, s_120_s2, 0, 0 },   /* 行 122 */
    { CMD_VOICE, 44, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 123 */
    { CMD_SAY, 0, 0, 0, s_empty, s_122_s2, 0, 0 },   /* 行 124 */
    { CMD_SAY, 0, 0, 0, s_empty, s_123_s2, 0, 0 },   /* 行 125 */
    { CMD_SAY, 0, 0, 0, s_empty, s_124_s2, 0, 0 },   /* 行 126 */
    { CMD_SAY, 0, 0, 0, s_empty, s_125_s2, 0, 0 },   /* 行 127 */
    { CMD_VOICE, 45, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 128 */
    { CMD_SAY, 0, 0, 0, s_empty, s_127_s2, 0, 0 },   /* 行 129 */
    { CMD_SAY, 0, 0, 0, s_empty, s_128_s2, 0, 0 },   /* 行 130 */
    { CMD_SAY, 0, 0, 0, s_empty, s_129_s2, 0, 0 },   /* 行 131 */
    { CMD_BG, 12, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 133 */
    { CMD_SAY, 0, 0, 0, s_131_s1, s_131_s2, 0, 0 },   /* 行 134 */
    { CMD_VOICE, 46, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 135 */
    { CMD_SAY, 0, 0, 0, s_empty, s_133_s2, 0, 0 },   /* 行 136 */
    { CMD_SAY, 0, 0, 0, s_empty, s_134_s2, 0, 0 },   /* 行 137 */
    { CMD_SAY, 0, 0, 0, s_135_s1, s_135_s2, 0, 0 },   /* 行 138 */
    { CMD_VOICE, 47, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 139 */
    { CMD_SAY, 0, 0, 0, s_137_s1, s_137_s2, 0, 0 },   /* 行 140 */
    { CMD_VOICE, 48, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 141 */
    { CMD_SAY, 0, 0, 0, s_139_s1, s_139_s2, 0, 0 },   /* 行 142 */
    { CMD_VOICE, 49, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 143 */
    { CMD_SAY, 0, 0, 0, s_141_s1, s_141_s2, 0, 0 },   /* 行 144 */
    { CMD_VOICE, 50, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 145 */
    { CMD_SAY, 0, 0, 0, s_empty, s_143_s2, 0, 0 },   /* 行 146 */
    { CMD_SAY, 0, 0, 0, s_empty, s_144_s2, 0, 0 },   /* 行 147 */
    { CMD_BG, 13, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 148 */
    { CMD_SAY, 0, 0, 0, s_146_s1, s_146_s2, 0, 0 },   /* 行 149 */
    { CMD_VOICE, 51, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 150 */
    { CMD_SAY, 0, 0, 0, s_empty, s_148_s2, 0, 0 },   /* 行 151 */
    { CMD_SAY, 0, 0, 0, s_empty, s_149_s2, 0, 0 },   /* 行 152 */
    { CMD_SAY, 0, 0, 0, s_150_s1, s_150_s2, 0, 0 },   /* 行 153 */
    { CMD_VOICE, 52, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 154 */
    { CMD_SAY, 0, 0, 0, s_152_s1, s_152_s2, 0, 0 },   /* 行 155 */
    { CMD_VOICE, 53, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 156 */
    { CMD_SAY, 0, 0, 0, s_154_s1, s_154_s2, 0, 0 },   /* 行 157 */
    { CMD_VOICE, 54, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 158 */
    { CMD_SAY, 0, 0, 0, s_156_s1, s_156_s2, 0, 0 },   /* 行 159 */
    { CMD_VOICE, 55, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 160 */
    { CMD_SAY, 0, 0, 0, s_158_s1, s_158_s2, 0, 0 },   /* 行 161 */
    { CMD_VOICE, 56, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 162 */
    { CMD_SAY, 0, 0, 0, s_160_s1, s_160_s2, 0, 0 },   /* 行 163 */
    { CMD_VOICE, 57, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 164 */
    { CMD_SAY, 0, 0, 0, s_162_s1, s_162_s2, 0, 0 },   /* 行 165 */
    { CMD_VOICE, 58, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 166 */
    { CMD_SAY, 0, 0, 0, s_164_s1, s_164_s2, 0, 0 },   /* 行 167 */
    { CMD_VOICE, 59, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 168 */
    { CMD_SAY, 0, 0, 0, s_166_s1, s_166_s2, 0, 0 },   /* 行 169 */
    { CMD_VOICE, 60, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 170 */
    { CMD_BG, 12, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 171 */
    { CMD_SAY, 0, 0, 0, s_empty, s_169_s2, 0, 0 },   /* 行 172 */
    { CMD_SAY, 0, 0, 0, s_170_s1, s_170_s2, 0, 0 },   /* 行 173 */
    { CMD_VOICE, 61, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 174 */
    { CMD_SAY, 0, 0, 0, s_172_s1, s_172_s2, 0, 0 },   /* 行 175 */
    { CMD_VOICE, 62, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 176 */
    { CMD_SAY, 0, 0, 0, s_174_s1, s_174_s2, 0, 0 },   /* 行 177 */
    { CMD_VOICE, 63, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 178 */
    { CMD_SAY, 0, 0, 0, s_176_s1, s_176_s2, 0, 0 },   /* 行 179 */
    { CMD_VOICE, 64, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 180 */
    { CMD_SAY, 0, 0, 0, s_178_s1, s_178_s2, 0, 0 },   /* 行 181 */
    { CMD_VOICE, 65, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 182 */
    { CMD_BG, 14, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 183 */
    { CMD_SAY, 0, 0, 0, s_empty, s_181_s2, 0, 0 },   /* 行 184 */
    { CMD_SAY, 0, 0, 0, s_empty, s_182_s2, 0, 0 },   /* 行 185 */
    { CMD_SAY, 0, 0, 0, s_empty, s_183_s2, 0, 0 },   /* 行 186 */
    { CMD_SAY, 0, 0, 0, s_empty, s_184_s2, 0, 0 },   /* 行 187 */
    { CMD_SAY, 0, 0, 0, s_empty, s_185_s2, 0, 0 },   /* 行 188 */
    { CMD_SAY, 0, 0, 0, s_empty, s_186_s2, 0, 0 },   /* 行 189 */
    { CMD_BG, 15, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 190 */
    { CMD_SAY, 0, 0, 0, s_188_s1, s_188_s2, 0, 0 },   /* 行 191 */
    { CMD_VOICE, 66, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 192 */
    { CMD_SAY, 0, 0, 0, s_190_s1, s_190_s2, 0, 0 },   /* 行 193 */
    { CMD_VOICE, 67, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 194 */
    { CMD_SAY, 0, 0, 0, s_empty, s_192_s2, 0, 0 },   /* 行 195 */
    { CMD_BG, 16, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 197 */
    { CMD_SAY, 0, 0, 0, s_empty, s_194_s2, 0, 0 },   /* 行 198 */
    { CMD_SAY, 0, 0, 0, s_empty, s_195_s2, 0, 0 },   /* 行 199 */
    { CMD_VOICE, 68, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 200 */
    { CMD_SAY, 0, 0, 0, s_empty, s_197_s2, 0, 0 },   /* 行 201 */
    { CMD_SAY, 0, 0, 0, s_198_s1, s_198_s2, 0, 0 },   /* 行 202 */
    { CMD_SAY, 0, 0, 0, s_199_s1, s_199_s2, 0, 0 },   /* 行 203 */
    { CMD_VOICE, 69, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 204 */
    { CMD_SAY, 0, 0, 0, s_201_s1, s_201_s2, 0, 0 },   /* 行 205 */
    { CMD_SAY, 0, 0, 0, s_202_s1, s_202_s2, 0, 0 },   /* 行 206 */
    { CMD_VOICE, 70, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 207 */
    { CMD_SAY, 0, 0, 0, s_204_s1, s_204_s2, 0, 0 },   /* 行 208 */
    { CMD_SAY, 0, 0, 0, s_205_s1, s_205_s2, 0, 0 },   /* 行 209 */
    { CMD_VOICE, 71, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 210 */
    { CMD_SAY, 0, 0, 0, s_207_s1, s_207_s2, 0, 0 },   /* 行 211 */
    { CMD_SAY, 0, 0, 0, s_208_s1, s_208_s2, 0, 0 },   /* 行 212 */
    { CMD_VOICE, 72, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 213 */
    { CMD_SAY, 0, 0, 0, s_empty, s_210_s2, 0, 0 },   /* 行 214 */
    { CMD_VOICE, 73, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 215 */
    { CMD_SAY, 0, 0, 0, s_empty, s_212_s2, 0, 0 },   /* 行 216 */
    { CMD_BG, 17, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 217 */
    { CMD_SAY, 0, 0, 0, s_214_s1, s_214_s2, 0, 0 },   /* 行 218 */
    { CMD_VOICE, 74, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 219 */
    { CMD_SAY, 0, 0, 0, s_216_s1, s_216_s2, 0, 0 },   /* 行 220 */
    { CMD_SAY, 0, 0, 0, s_217_s1, s_217_s2, 0, 0 },   /* 行 221 */
    { CMD_VOICE, 75, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 222 */
    { CMD_SAY, 0, 0, 0, s_219_s1, s_219_s2, 0, 0 },   /* 行 223 */
    { CMD_SAY, 0, 0, 0, s_empty, s_220_s2, 0, 0 },   /* 行 224 */
    { CMD_SAY, 0, 0, 0, s_empty, s_221_s2, 0, 0 },   /* 行 225 */
    { CMD_SAY, 0, 0, 0, s_222_s1, s_222_s2, 0, 0 },   /* 行 226 */
    { CMD_SAY, 0, 0, 0, s_223_s1, s_223_s2, 0, 0 },   /* 行 227 */
    { CMD_VOICE, 76, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 228 */
    { CMD_SAY, 0, 0, 0, s_225_s1, s_225_s2, 0, 0 },   /* 行 229 */
    { CMD_SAY, 0, 0, 0, s_226_s1, s_226_s2, 0, 0 },   /* 行 230 */
    { CMD_VOICE, 77, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 231 */
    { CMD_SAY, 0, 0, 0, s_228_s1, s_228_s2, 0, 0 },   /* 行 232 */
    { CMD_SAY, 0, 0, 0, s_229_s1, s_229_s2, 0, 0 },   /* 行 233 */
    { CMD_VOICE, 78, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 234 */
    { CMD_SAY, 0, 0, 0, s_231_s1, s_231_s2, 0, 0 },   /* 行 235 */
    { CMD_SAY, 0, 0, 0, s_232_s1, s_232_s2, 0, 0 },   /* 行 236 */
    { CMD_VOICE, 79, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 237 */
    { CMD_SAY, 0, 0, 0, s_empty, s_234_s2, 0, 0 },   /* 行 238 */
    { CMD_SAY, 0, 0, 0, s_235_s1, s_235_s2, 0, 0 },   /* 行 239 */
    { CMD_SAY, 0, 0, 0, s_236_s1, s_236_s2, 0, 0 },   /* 行 240 */
    { CMD_VOICE, 80, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 241 */
    { CMD_SAY, 0, 0, 0, s_238_s1, s_238_s2, 0, 0 },   /* 行 242 */
    { CMD_SAY, 0, 0, 0, s_empty, s_239_s2, 0, 0 },   /* 行 243 */
    { CMD_BG, 18, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 244 */
    { CMD_SAY, 0, 0, 0, s_empty, s_241_s2, 0, 0 },   /* 行 245 */
    { CMD_VOICE, 81, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 246 */
    { CMD_SAY, 0, 0, 0, s_empty, s_243_s2, 0, 0 },   /* 行 247 */
    { CMD_SAY, 0, 0, 0, s_empty, s_244_s2, 0, 0 },   /* 行 248 */
    { CMD_SAY, 0, 0, 0, s_245_s1, s_245_s2, 0, 0 },   /* 行 249 */
    { CMD_VOICE, 82, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 250 */
    { CMD_SAY, 0, 0, 0, s_empty, s_247_s2, 0, 0 },   /* 行 251 */
    { CMD_SAY, 0, 0, 0, s_empty, s_248_s2, 0, 0 },   /* 行 252 */
    { CMD_VOICE, 83, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 253 */
    { CMD_SAY, 0, 0, 0, s_250_s1, s_250_s2, 0, 0 },   /* 行 254 */
    { CMD_VOICE, 84, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 255 */
    { CMD_SAY, 0, 0, 0, s_252_s1, s_252_s2, 0, 0 },   /* 行 256 */
    { CMD_SAY, 0, 0, 0, s_empty, s_253_s2, 0, 0 },   /* 行 257 */
    { CMD_SAY, 0, 0, 0, s_254_s1, s_254_s2, 0, 0 },   /* 行 258 */
    { CMD_VOICE, 85, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 259 */
    { CMD_SAY, 0, 0, 0, s_empty, s_256_s2, 0, 0 },   /* 行 260 */
    { CMD_VOICE, 86, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 261 */
    { CMD_SAY, 0, 0, 0, s_empty, s_258_s2, 0, 0 },   /* 行 262 */
    { CMD_SAY, 0, 0, 0, s_empty, s_259_s2, 0, 0 },   /* 行 263 */
    { CMD_SAY, 0, 0, 0, s_empty, s_260_s2, 0, 0 },   /* 行 264 */
    { CMD_SAY, 0, 0, 0, s_261_s1, s_261_s2, 0, 0 },   /* 行 265 */
    { CMD_SAY, 0, 0, 0, s_262_s1, s_262_s2, 0, 0 },   /* 行 266 */
    { CMD_VOICE, 87, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 267 */
    { CMD_SAY, 0, 0, 0, s_empty, s_264_s2, 0, 0 },   /* 行 268 */
    { CMD_SAY, 0, 0, 0, s_265_s1, s_265_s2, 0, 0 },   /* 行 269 */
    { CMD_SAY, 0, 0, 0, s_empty, s_266_s2, 0, 0 },   /* 行 270 */
    { CMD_SAY, 0, 0, 0, s_267_s1, s_267_s2, 0, 0 },   /* 行 271 */
    { CMD_VOICE, 88, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 272 */
    { CMD_SAY, 0, 0, 0, s_empty, s_269_s2, 0, 0 },   /* 行 273 */
    { CMD_BG, 17, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 274 */
    { CMD_SAY, 0, 0, 0, s_271_s1, s_271_s2, 0, 0 },   /* 行 275 */
    { CMD_VOICE, 89, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 276 */
    { CMD_SAY, 0, 0, 0, s_273_s1, s_273_s2, 0, 0 },   /* 行 277 */
    { CMD_VOICE, 90, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 278 */
    { CMD_SAY, 0, 0, 0, s_275_s1, s_275_s2, 0, 0 },   /* 行 279 */
    { CMD_VOICE, 91, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 280 */
    { CMD_SAY, 0, 0, 0, s_277_s1, s_277_s2, 0, 0 },   /* 行 281 */
    { CMD_VOICE, 92, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 282 */
    { CMD_SAY, 0, 0, 0, s_empty, s_279_s2, 0, 0 },   /* 行 283 */
    { CMD_SAY, 0, 0, 0, s_280_s1, s_280_s2, 0, 0 },   /* 行 284 */
    { CMD_VOICE, 93, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 285 */
    { CMD_SAY, 0, 0, 0, s_282_s1, s_282_s2, 0, 0 },   /* 行 286 */
    { CMD_VOICE, 94, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 287 */
    { CMD_SAY, 0, 0, 0, s_284_s1, s_284_s2, 0, 0 },   /* 行 288 */
    { CMD_VOICE, 95, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 289 */
    { CMD_SAY, 0, 0, 0, s_286_s1, s_286_s2, 0, 0 },   /* 行 290 */
    { CMD_VOICE, 96, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 291 */
    { CMD_SAY, 0, 0, 0, s_empty, s_288_s2, 0, 0 },   /* 行 292 */
    { CMD_SAY, 0, 0, 0, s_289_s1, s_289_s2, 0, 0 },   /* 行 293 */
    { CMD_VOICE, 97, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 294 */
    { CMD_SAY, 0, 0, 0, s_291_s1, s_291_s2, 0, 0 },   /* 行 295 */
    { CMD_VOICE, 98, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 296 */
    { CMD_SAY, 0, 0, 0, s_293_s1, s_293_s2, 0, 0 },   /* 行 297 */
    { CMD_VOICE, 99, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 298 */
    { CMD_SAY, 0, 0, 0, s_295_s1, s_295_s2, 0, 0 },   /* 行 299 */
    { CMD_VOICE, 100, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 300 */
    { CMD_SAY, 0, 0, 0, s_297_s1, s_297_s2, 0, 0 },   /* 行 301 */
    { CMD_VOICE, 101, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 302 */
    { CMD_SAY, 0, 0, 0, s_299_s1, s_299_s2, 0, 0 },   /* 行 303 */
    { CMD_VOICE, 102, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 304 */
    { CMD_SAY, 0, 0, 0, s_301_s1, s_301_s2, 0, 0 },   /* 行 305 */
    { CMD_VOICE, 103, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 306 */
    { CMD_SAY, 0, 0, 0, s_303_s1, s_303_s2, 0, 0 },   /* 行 307 */
    { CMD_VOICE, 104, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 308 */
    { CMD_SAY, 0, 0, 0, s_305_s1, s_305_s2, 0, 0 },   /* 行 309 */
    { CMD_VOICE, 105, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 310 */
    { CMD_SAY, 0, 0, 0, s_empty, s_307_s2, 0, 0 },   /* 行 311 */
    { CMD_SAY, 0, 0, 0, s_empty, s_308_s2, 0, 0 },   /* 行 312 */
    { CMD_SAY, 0, 0, 0, s_empty, s_309_s2, 0, 0 },   /* 行 313 */
    { CMD_SAY, 0, 0, 0, s_310_s1, s_310_s2, 0, 0 },   /* 行 314 */
    { CMD_SAY, 0, 0, 0, s_311_s1, s_311_s2, 0, 0 },   /* 行 315 */
    { CMD_VOICE, 106, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 316 */
    { CMD_SAY, 0, 0, 0, s_313_s1, s_313_s2, 0, 0 },   /* 行 317 */
    { CMD_SAY, 0, 0, 0, s_314_s1, s_314_s2, 0, 0 },   /* 行 318 */
    { CMD_VOICE, 107, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 319 */
    { CMD_SAY, 0, 0, 0, s_316_s1, s_316_s2, 0, 0 },   /* 行 320 */
    { CMD_VOICE, 108, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 321 */
    { CMD_SAY, 0, 0, 0, s_318_s1, s_318_s2, 0, 0 },   /* 行 322 */
    { CMD_SAY, 0, 0, 0, s_319_s1, s_319_s2, 0, 0 },   /* 行 323 */
    { CMD_VOICE, 109, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 324 */
    { CMD_BG, 19, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 325 */
    { CMD_SAY, 0, 0, 0, s_empty, s_322_s2, 0, 0 },   /* 行 326 */
    { CMD_SAY, 0, 0, 0, s_empty, s_323_s2, 0, 0 },   /* 行 327 */
    { CMD_SAY, 0, 0, 0, s_empty, s_324_s2, 0, 0 },   /* 行 328 */
    { CMD_SAY, 0, 0, 0, s_empty, s_325_s2, 0, 0 },   /* 行 329 */
    { CMD_SAY, 0, 0, 0, s_326_s1, s_326_s2, 0, 0 },   /* 行 330 */
    { CMD_SAY, 0, 0, 0, s_327_s1, s_327_s2, 0, 0 },   /* 行 331 */
    { CMD_VOICE, 110, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 332 */
    { CMD_SAY, 0, 0, 0, s_329_s1, s_329_s2, 0, 0 },   /* 行 333 */
    { CMD_SAY, 0, 0, 0, s_empty, s_330_s2, 0, 0 },   /* 行 334 */
    { CMD_SAY, 0, 0, 0, s_331_s1, s_331_s2, 0, 0 },   /* 行 335 */
    { CMD_VOICE, 111, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 336 */
    { CMD_SAY, 0, 0, 0, s_333_s1, s_333_s2, 0, 0 },   /* 行 337 */
    { CMD_SAY, 0, 0, 0, s_334_s1, s_334_s2, 0, 0 },   /* 行 338 */
    { CMD_VOICE, 112, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 339 */
    { CMD_END, 0, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 341 */
    { CMD_END, 0, 0, 0, s_empty, s_empty, 0, 0 },   /* 行 0 */
};

const int scenario_count = 338;

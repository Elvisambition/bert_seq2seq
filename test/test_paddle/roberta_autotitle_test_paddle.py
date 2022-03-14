import sys
sys.path.append("/home/bert_seq2seq/paddle_model")
import paddle
import numpy as np
from paddle import nn
from paddlenlp.transformers import AutoTokenizer, AutoModel, BertModel, BertTokenizer, CTRLTokenizer,RobertaTokenizer,RobertaModel
from paddlenlp.transformers.roberta.modeling import robertaSeq2Seq
from paddlenlp.transformers.roberta.modeling import RobertaPretrainedModel
import paddle.nn.functional as F
from tqdm import tqdm
from paddle.io import Dataset

class Predictor:

    def __init__(self, model: BertModel, tokenizer: BertTokenizer, out_max_length=100, beam_size=1, max_length=512, ):
        self.out_max_length = out_max_length
        self.beam_size = beam_size
        self.max_length = max_length
        self.tokenizer = tokenizer
        self.model = model

    def generate(self, text):
        self.model.eval()
        input_max_length = self.max_length - self.out_max_length
        tokenizer_out = self.tokenizer.encode(text, max_seq_len=input_max_length)
        vocab = self.tokenizer.vocab
        token_ids = tokenizer_out["input_ids"]
        token_type_ids = tokenizer_out["token_type_ids"]
        token_ids = paddle.to_tensor(token_ids).reshape([1, -1])
        token_type_ids = paddle.to_tensor(token_type_ids).reshape([1, -1])

        # print(f"token_ids is {token_ids}")
        out_puts_ids = self.beam_search(token_ids, token_type_ids, vocab, beam_size=self.beam_size)
        # print(out_puts_ids)
        tokens = self.tokenizer.convert_ids_to_tokens(out_puts_ids)

        return self.tokenizer.convert_tokens_to_string(tokens)

    def beam_search(self, token_ids, token_type_ids, word2ix, beam_size=1, ):
        """
        beam-search操作
        """
        sep_id = word2ix["[SEP]"]

        # 用来保存输出序列
        # output_ids = paddle.empty([1, 0]).astype("int")
        output_ids = None
        # output_ids = np.empty([1, 0]).astype(np.int)
        # 用来保存累计得分
        with paddle.no_grad():
            output_scores = np.zeros([token_ids.shape[0]])
            for step in range(self.out_max_length):
                if step == 0:
                    scores = self.model(token_ids, token_type_ids)
                    # 重复beam-size次 输入ids
                    token_ids = np.tile(token_ids.reshape([1, -1]), [beam_size, 1])
                    token_type_ids = np.tile(token_type_ids.reshape([1, -1]), [beam_size, 1])
                else:
                    scores = self.model(new_input_ids, new_token_type_ids)

                logit_score = F.log_softmax(scores[:, -1], axis=-1).numpy()

                logit_score = output_scores.reshape([-1, 1]) + logit_score  # 累计得分
                ## 取topk的时候我们是展平了然后再去调用topk函数
                # 展平
                logit_score = logit_score.reshape([-1])
                hype_pos = np.argpartition(logit_score, -beam_size, axis=-1)[-beam_size:]
                hype_score = logit_score[hype_pos]
                indice1 = (hype_pos // scores.shape[-1]).reshape([-1])  # 行索引
                indice2 = (hype_pos % scores.shape[-1]).astype(np.int).reshape([-1, 1])  # 列索引

                output_scores = hype_score
                if output_ids is None:
                    output_ids = indice2.reshape([beam_size, 1])
                else:
                    output_ids = np.concatenate([output_ids[indice1], indice2], axis=1).astype(np.int)

                new_input_ids = np.concatenate([token_ids, output_ids], axis=1)
                new_token_type_ids = np.concatenate([token_type_ids, np.ones_like(output_ids)], axis=1)

                end_counts = (output_ids == sep_id).sum(1)  # 统计出现的end标记
                best_one = output_scores.argmax()
                if end_counts[best_one] == 1:
                    # 说明出现终止了～
                    return output_ids[best_one][:-1]
                else:
                    # 保留未完成部分
                    flag = (end_counts < 1)  # 标记未完成序列
                    if not flag.all():  # 如果有已完成的
                        token_ids = token_ids[flag]
                        token_type_ids = token_type_ids[flag]
                        new_input_ids = new_input_ids[flag]
                        new_token_type_ids = new_token_type_ids[flag]
                        output_ids = output_ids[flag]  # 扔掉已完成序列
                        output_scores = output_scores[flag]  # 扔掉已完成序列
                        beam_size = flag.sum()  # topk相应变化

            return output_ids[output_scores.argmax()]

def returnForecast(data,modelAddress = None,tokenizerAddress = None):

    if modelAddress is None:
        model = robertaSeq2Seq.from_pretrained('./model')

    else:
        model = robertaSeq2Seq.from_pretrained(modelAddress)


    if tokenizerAddress is None:
        tokenizer = RobertaTokenizer.from_pretrained('./tokenizer')

    else:
        tokenizer = RobertaTokenizer.from_pretrained(tokenizerAddress)

    predictor = Predictor(model, tokenizer, beam_size=2, out_max_length=40, max_length=512)


    import collections


    OutCouplet = {}

    OutCouplet = collections.OrderedDict()

    for simply_in in data:

        out = predictor.generate(simply_in)
        OutCouplet[simply_in] = out

    return OutCouplet

def forecastForAutoTitle(data,modelAddress = None,tokenizerAddress = None):

    Couplet = returnForecast(data,modelAddress,tokenizerAddress)

    for Uplink,Downlink in Couplet.items():

        print(f"新闻：{Uplink}，标题：{Downlink}。")



            

if __name__ == '__main__':

    test_data = [
                    "本文总结了十个可穿戴产品的设计原则而这些原则同样也是笔者认为是这个行业最吸引人的地方1为人们解决重复性问题2从人开始而不是从机器开始3要引起注意但不要刻意4提升用户能力而不是取代人",
                    "2007年乔布斯向人们展示iPhone并宣称它将会改变世界还有人认为他在夸大其词然而在8年后以iPhone为代表的触屏智能手机已经席卷全球各个角落未来智能手机将会成为真正的个人电脑为人类发展做出更大的贡献",
                    "雅虎发布2014年第四季度财报并推出了免税方式剥离其持有的阿里巴巴集团15％股权的计划打算将这一价值约400亿美元的宝贵投资分配给股东截止发稿前雅虎股价上涨了大约7％至5145美元"]

    forecastForAutoTitle(test_data)





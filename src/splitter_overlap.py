'''
Author: Dean
Date: 2023-12-14 11:06:31
LastEditTime: 2024-05-15 19:51:21
LastEditors: your name
Description: 
FilePath: \python\askgraphkbqa\text_splitter\splitter_overlap.py
可以输入预定的版权声明、个性签名、空行等
'''
import re
from typing import List, Optional, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging

logger = logging.getLogger(__name__)

def _split_text_with_regex_from_end(
        text: str, separator: str, keep_separator: bool
) -> List[str]:
    # Now that we have the separator, split the text
    if separator:
        if keep_separator:
            # The parentheses in the pattern keep the delimiters in the result.
            _splits = re.split(f"({separator})", text)
            splits = ["".join(i) for i in zip(_splits[0::2], _splits[1::2])]
            if len(_splits) % 2 == 1:
                splits += _splits[-1:]
            # splits = [_splits[0]] + splits
        else:
            splits = re.split(separator, text)
    else:
        splits = list(text)
    return [s for s in splits if s != ""]

def is_all_Upper(s):
    """判断s中所有的英文字符是否全部大写，非英文字符不做判断"""
    return all([c.isupper() or not c.isalpha() for c in s])

def is_end_of_sentence(s):
    """判断是否为句子的结尾"""
    s = s.strip()
    if s == '' or is_all_Upper(s):
        return True
    return s[-1] in ['.', '!', '?', ';', ':', '\\', '/', '{','}','|','│']

class RecursiveTextSplitter(RecursiveCharacterTextSplitter):
    def __init__(
            self,
            separators: Optional[List[str]] = None,
            keep_separator: bool = True,
            is_separator_regex: bool = True,
            **kwargs: Any,
    ) -> None:
        """Create a new TextSplitter."""
        super().__init__(keep_separator=keep_separator, **kwargs)
        self._separators_chinese = separators or [
            "\n\n",
            "\n",
            "。|！|？",
            "；|，",
            "\.|\!|\?",
            ";|,",
            " "
        ]
        self._separators_none_chinese = separators or [
            "\n\n",
            "\n", 
            "\.|\?|\!", 
            ";|,",
            "。|！|？", 
            "；|，",
            " "
        ]
        self._is_separator_regex = is_separator_regex
        self.min_overlap = self._chunk_overlap // 2
        
    def _slice_text(self, text, slice_length, overlap_length):
        """
        将文本切片
        :param text: 文本
        :param slice_length: 切片长度
        :param overlap_length: 重叠长度
        :return: 切片列表
        """
        start = 0
        slices = []
        while start < len(text):
            end = start + slice_length
            if end > len(text):
                end = len(text)
            slices.append(text[start:end])
            start += slice_length - overlap_length
        return slices
    
    def is_special(self, char: str) -> bool:
        """判断是否为特殊字符"""
        return char in ['。', '，', '；', '！', '？', '、', '：', '“', '”', '‘', '’', '《', '》', '（', '）', '【', '】', '—', '…', '·', '「', '」', '『', '』', '〈', '〉', '﹁', '﹂', '﹃', '﹄', '﹏', '﹐', '﹑', '﹒', '﹔', '﹕', '﹖', '﹗', '﹘', '﹙', '﹚', '﹛', '﹜', '﹝', '﹞', '﹟', '﹠', '﹡', '﹢', '﹣', '﹤', '﹥', '﹦', '﹨', '﹩', '﹪', '﹫', '！', '？', '｡', '。', '､', '、', '，', '；', '：']
    
    def is_chinese(self, char: str) -> bool:
        """判断是否为中文"""
        return '\u4e00' <= char <= '\u9fff'
    


    def split_text(self, text: str) -> List[str]:
        """Split incoming text and return chunks."""

        # Get appropriate separator to use
        cnt_chinese = 0
        cnt_none_chinese = 0
        for char in text:
            if self.is_special(char):
                continue
            if self.is_chinese(char):
                cnt_chinese += 1
            else:
                cnt_none_chinese += 1
        if cnt_chinese > cnt_none_chinese:
            _separators = self._separators_chinese
        else:
            _separators = self._separators_none_chinese
            # 合并多行为一行
            lines = text.split('\n')
            text = ''
            pre = ''
            for line in lines:
                line_strip = line.strip()
                if is_end_of_sentence(pre):
                    if line_strip != '':
                        text += '\n' + line
                else:
                    if pre[-1] == '-':
                        if line_strip != '':
                            text += line
                    else:
                        if line_strip != '':
                            text += ' ' + line_strip
                pre = line_strip

        chunks = self._split_text(text, _separators, self._chunk_size)
        final_overlaped_chunks = []
        slice_chunk = ''
        for i, chunk in enumerate(chunks):
            if len(slice_chunk) + len(chunk) < self._chunk_size:
                slice_chunk += chunk
            else:
                # print('slice_chunk:',len(slice_chunk), slice_chunk)
                # 过短情况处理
                if len(slice_chunk) > self._chunk_overlap:
                    final_overlaped_chunks.append(slice_chunk)
                    len_overlap_slices = 0
                else:
                    final_overlaped_chunks.append(slice_chunk + chunk[:self._chunk_overlap - len(slice_chunk)])
                    len_overlap_slices = self._chunk_overlap - len(slice_chunk)
                overlap_slices = []

                for j in range(i - 1, -1, -1):
                    if len_overlap_slices + len(chunks[j]) < self._chunk_overlap:
                        overlap_slices.append(chunks[j])
                        len_overlap_slices += len(chunks[j])
                    else:
                        break
                small_chunks = chunks[:j + 1]
                
                while len_overlap_slices < self.min_overlap and j >= 0:
                    small_chunks = self._split_text(''.join(small_chunks[j]), _separators, self._chunk_overlap - len_overlap_slices)
                    for k in range(len(small_chunks) - 1, -1, -1):
                        if len_overlap_slices + len(small_chunks[k]) < self._chunk_overlap:
                            len_overlap_slices += len(small_chunks[k])
                            overlap_slices.append(small_chunks[k])
                        else:
                            break
                    small_chunks = small_chunks[:k + 1]
                    j = k - 1
                overlap_slices.reverse()
                slice_chunk = ' '.join(overlap_slices) + chunk
        if slice_chunk != '':
            final_overlaped_chunks.append(slice_chunk)
        return final_overlaped_chunks
    
    def _split_text(self, text: str, separators: List[str], chunk_size: int) -> List[str]:
        """Split incoming text and return chunks."""
        final_chunks = []
        # Get appropriate separator to use
        separator = separators[-1]
        new_separators = []
        for i, _s in enumerate(separators):
            _separator = _s if self._is_separator_regex else re.escape(_s)
            if _s == "":
                separator = _s
                break
            if re.search(_separator, text):
                separator = _s
                new_separators = separators[i + 1:]
                break

        _separator = separator if self._is_separator_regex else re.escape(separator)
        splits = _split_text_with_regex_from_end(text, _separator, self._keep_separator)

        # Now go merging things, recursively splitting longer texts.
        _separator = "" if self._keep_separator else separator
        for s in splits:
            if self._length_function(s) < chunk_size:
                final_chunks.append(s)
            else:
                if not new_separators:
                    final_chunks.extend(self._slice_text(s, chunk_size, 0))
                else:
                    other_info = self._split_text(s, new_separators, chunk_size)
                    final_chunks.extend(other_info)
        
        return [re.sub(r"\n{2,}", "\n", chunk.strip(' ') if separator != ' ' else chunk) for chunk in final_chunks if chunk.strip()!=""]


if __name__ == "__main__":
    text_splitter = RecursiveTextSplitter(
        keep_separator=True,
        is_separator_regex=True,
        chunk_size=512,
        chunk_overlap=96
    )
    ls = [
        # """中国对外贸易形势报告（75页）。前 10 个月，一般贸易进出口 19.5 万亿元，增长 25.1%， 比整体进出口增速高出 2.9 个百分点，占进出口总额的 61.7%，较去年同期提升 1.6 个百分点。其中，一般贸易出口 10.6 万亿元，增长 25.3%，占出口总额的 60.9%，提升 1.5 个百分点；进口8.9万亿元，增长24.9%，占进口总额的62.7%， 提升 1.8 个百分点。加工贸易进出口 6.8 万亿元，增长 11.8%， 占进出口总额的 21.5%，减少 2.0 个百分点。其中，出口增 长 10.4%，占出口总额的 24.3%，减少 2.6 个百分点；进口增 长 14.2%，占进口总额的 18.0%，减少 1.2 个百分点。此外， 以保税物流方式进出口 3.96 万亿元，增长 27.9%。其中，出 口 1.47 万亿元，增长 38.9%；进口 2.49 万亿元，增长 22.2%。前三季度，中国服务贸易继续保持快速增长态势。服务 进出口总额 37834.3 亿元，增长 11.6%；其中服务出口 17820.9 亿元，增长 27.3%；进口 20013.4 亿元，增长 0.5%，进口增 速实现了疫情以来的首次转正。服务出口增幅大于进口 26.8 个百分点，带动服务贸易逆差下降 62.9%至 2192.5 亿元。服 务贸易结构持续优化，知识密集型服务进出口 16917.7 亿元， 增长 13.3%，占服务进出口总额的比重达到 44.7%，提升 0.7 个百分点。 二、中国对外贸易发展环境分析和展望 全球疫情起伏反复，经济复苏分化加剧，大宗商品价格 上涨、能源紧缺、运力紧张及发达经济体政策调整外溢等风 险交织叠加。同时也要看到，我国经济长期向好的趋势没有 改变，外贸企业韧性和活力不断增强，新业态新模式加快发 展，创新转型步伐提速。产业链供应链面临挑战。美欧等加快出台制造业回迁计 划，加速产业链供应链本土布局，跨国公司调整产业链供应 链，全球双链面临新一轮重构，区域化、近岸化、本土化、 短链化趋势凸显。疫苗供应不足，制造业“缺芯”、物流受限、 运价高企，全球产业链供应链面临压力。 全球通胀持续高位运行。能源价格上涨加大主要经济体 的通胀压力，增加全球经济复苏的不确定性。世界银行今年 10 月发布《大宗商品市场展望》指出，能源价格在 2021 年 大涨逾 80%，并且仍将在 2022 年小幅上涨。IMF 指出，全 球通胀上行风险加剧，通胀前景存在巨大不确定性。""",
        # """China's Foreign Trade Situation Report (75 pages). In the first 10 months, the general trade import and export of 19.5 trillion yuan, an increase of 25.1%, 2.9 percentage points higher than the overall import and export growth rate, accounting for 61.7% of the total import and export, an increase of 1.6 percentage points over the same period last year. Among them, the general trade export was 10.6 trillion yuan, an increase of 25.3%, accounting for 60.9% of the total export, an increase of 1.5 percentage points; Imports reached 8.9 trillion yuan, up 24.9%, accounting for 62.7% of the total imports, an increase of 1.8 percentage points. The import and export of processing trade reached 6.8 trillion yuan, an increase of 11.8%, accounting for 21.5% of the total import and export volume, a decrease of 2.0 percentage points. Among them, exports increased by 10.4%, accounting for 24.3% of the total exports, a decrease of 2.6 percentage points; Imports increased by 14.2%, accounting for 18.0% of the total imports, a decrease of 1.2 percentage points. In addition, the import and export of bonded logistics totaled 3.96 trillion yuan, an increase of 27.9 percent. Of this total, exports amounted to 1.47 trillion yuan, an increase of 38.9%; Imports reached 2.49 trillion yuan, up 22.2%. In the first three quarters, China's service trade continued to maintain rapid growth. The total value of imports and exports of services was 3,783.43 billion yuan, up by 11.6 percent; In total, the export of services was 1,782.09 billion yuan, up by 27.3%; Imports reached 2001.34 billion yuan, up 0.5%, and the growth rate of imports turned positive for the first time since the epidemic. Service exports increased by 26.8 percentage points more than imports, driving the service trade deficit down 62.9 percent to 219.25 billion yuan. The structure of service trade continued to improve, with the import and export of knowledge-intensive services reaching 1691.77 billion yuan, up 13.3%, accounting for 44.7% of the total import and export of services, up 0.7 percentage points. Ii. Analysis and outlook of the Environment for the development of China's Foreign Trade The ups and downs of the global epidemic, the divergence of economic recovery, rising commodity prices, energy shortages, transport capacity constraints and spillover from policy adjustments in developed economies are intertwined. At the same time, we should note that the long-term positive trend of the Chinese economy has not changed, the resilience and vitality of foreign trade enterprises are increasing, the development of new forms and models of business is accelerating, and the pace of innovation and transformation is accelerating. Industrial and supply chains face challenges. The United States and Europe have accelerated the introduction of manufacturing relocation plans, accelerated the local layout of industrial chain and supply chain, and multinational companies have adjusted industrial chain and supply chain, and the global double chain is facing a new round of restructuring, and the trend of regionalization, nearshore, localization, and short chain is prominent. The supply of vaccines is insufficient, the manufacturing industry is "short of core", logistics is limited, and freight rates are high, and the global industrial chain and supply chain are under pressure. Global inflation remains high. Rising energy prices add to inflationary pressures in major economies and add uncertainty to the global economic recovery. According to the World Bank's Commodity Market Outlook released in October, energy prices will surge more than 80% in 2021 and will continue to rise slightly in 2022. The IMF noted that upside risks to global inflation have intensified and there are significant uncertainties in the inflation outlook."""
        """
DESCRIPTION
       Linux  uses David L. Mills' clock adjustment algorithm (see RFC 5905).  The system call adjtimex() reads and optionally sets adjust‐
       ment parameters for this algorithm.  It takes a pointer to a timex structure, updates kernel parameters from (selected)  field  val‐
       ues, and returns the same structure updated with the current kernel values.  This structure is declared as follows:

           struct timex {
               int  modes;      /* Mode selector */
               long offset;     /* Time offset; nanoseconds, if STA_NANO
                                   status flag is set, otherwise
                                   microseconds */
               long freq;       /* Frequency offset; see NOTES for units */
               long maxerror;   /* Maximum error (microseconds) */
               long esterror;   /* Estimated error (microseconds) */
               int  status;     /* Clock command/status */
               long constant;   /* PLL (phase-locked loop) time constant */
               long precision;  /* Clock precision
                                   (microseconds, read-only) */
               long tolerance;  /* Clock frequency tolerance (read-only);
                                   see NOTES for units */
               struct timeval time;
                                /* Current time (read-only, except for
                                   ADJ_SETOFFSET); upon return, time.tv_usec
                                   contains nanoseconds, if STA_NANO status
                                   flag is set, otherwise microseconds */
               long tick;       /* Microseconds between clock ticks */
               long ppsfreq;    /* PPS (pulse per second) frequency
                                   (read-only); see NOTES for units */
               long jitter;     /* PPS jitter (read-only); nanoseconds, if
                                   STA_NANO status flag is set, otherwise
                                   microseconds */
               int  shift;      /* PPS interval duration
                                   (seconds, read-only) */
               long stabil;     /* PPS stability (read-only);
                                   see NOTES for units */
               long jitcnt;     /* PPS count of jitter limit exceeded
                                   events (read-only) */
               long calcnt;     /* PPS count of calibration intervals
                                   (read-only) */
               long errcnt;     /* PPS count of calibration errors
                                   (read-only) */
               long stbcnt;     /* PPS count of stability limit exceeded
                                   events (read-only) */
               int tai;         /* TAI offset, as set by previous ADJ_TAI
                                   operation (seconds, read-only,
                                   since Linux 2.6.26) */
               /* Further padding bytes to allow for future expansion */
           };

       The modes field determines which parameters, if any, to set.  (As described later in this page, the constants used for ntp_adjtime()
       are equivalent but differently named.)  It is a bit mask containing a bitwise-or combination of zero or more of the following bits:

       ADJ_OFFSET
              Set time offset from buf.offset.  Since Linux 2.6.26, the supplied value is clamped to the range (-0.5s,  +0.5s).   In  older
              kernels, an EINVAL error occurs if the supplied value is out of range.

       ADJ_FREQUENCY
              Set  frequency  offset from buf.freq.  Since Linux 2.6.26, the supplied value is clamped to the range (-32768000, +32768000).
              In older kernels, an EINVAL error occurs if the supplied value is out of range.

       ADJ_MAXERROR
              Set maximum time error from buf.maxerror.

       ADJ_ESTERROR
              Set estimated time error from buf.esterror.

       ADJ_STATUS
              Set clock status bits from buf.status.  A description of these bits is provided below.

       ADJ_TIMECONST
              Set PLL time constant from buf.constant.  If the STA_NANO status flag (see below) is clear, the kernel adds 4 to this value.

       ADJ_SETOFFSET (since Linux 2.6.39)
              Add buf.time to the current time.  If buf.status includes the ADJ_NANO  flag,  then  buf.time.tv_usec  is  interpreted  as  a
              nanosecond value; otherwise it is interpreted as microseconds.

              The value of buf.time is the sum of its two fields, but the field buf.time.tv_usec must always be nonnegative.  The following
              example shows how to normalize a timeval with nanosecond resolution.

                  while (buf.time.tv_usec < 0) {
                      buf.time.tv_sec  -= 1;
                      buf.time.tv_usec += 1000000000;
                  }

       ADJ_MICRO (since Linux 2.6.26)
              Select microsecond resolution.

       ADJ_NANO (since Linux 2.6.26)
              Select nanosecond resolution.  Only one of ADJ_MICRO and ADJ_NANO should be specified.

       ADJ_TAI (since Linux 2.6.26)
              Set TAI (Atomic International Time) offset from buf.constant.

              ADJ_TAI should not be used in conjunction with ADJ_TIMECONST, since the latter mode also employs the buf.constant field.

              For a complete explanation of TAI and the difference between TAI and UTC, see BIPM ⟨http://www.bipm.org/en/bipm/tai/tai.html⟩

       ADJ_TICK
              Set tick value from buf.tick.

       Alternatively, modes can be specified as either of the following (multibit mask) values, in which case  other  bits  should  not  be
       specified in modes:

       ADJ_OFFSET_SINGLESHOT
              Old-fashioned  adjtime(3):  (gradually)  adjust  time  by value specified in buf.offset, which specifies an adjustment in mi‐
              croseconds.

       ADJ_OFFSET_SS_READ (functional since Linux 2.6.28)
              Return (in buf.offset) the remaining amount of time to be adjusted after an earlier  ADJ_OFFSET_SINGLESHOT  operation.   This
              feature was added in Linux 2.6.24, but did not work correctly until Linux 2.6.28.

       Ordinary users are restricted to a value of either 0 or ADJ_OFFSET_SS_READ for modes.  Only the superuser may set any parameters.

       The  buf.status  field  is  a bit mask that is used to set and/or retrieve status bits associated with the NTP implementation.  Some
       bits in the mask are both readable and settable, while others are read-only.

       STA_PLL (read-write)
              Enable phase-locked loop (PLL) updates via ADJ_OFFSET.

       STA_PPSFREQ (read-write)
              Enable PPS (pulse-per-second) frequency discipline.

       STA_PPSTIME (read-write)
              Enable PPS time discipline.

       STA_FLL (read-write)
              Select frequency-locked loop (FLL) mode.

       STA_INS (read-write)
              Insert a leap second after the last second of the UTC day, thus extending the last minute of the day by  one  second.   Leap-
              second insertion will occur each day, so long as this flag remains set.

       STA_DEL (read-write)
              Delete  a  leap second at the last second of the UTC day.  Leap second deletion will occur each day, so long as this flag re‐
              mains set.

       STA_UNSYNC (read-write)
              Clock unsynchronized.

       STA_FREQHOLD (read-write)
              Hold frequency.  Normally adjustments made via ADJ_OFFSET result in dampened frequency adjustments also  being  made.   So  a
              single  call  corrects  the current offset, but as offsets in the same direction are made repeatedly, the small frequency ad‐
              justments will accumulate to fix the long-term skew.

              This flag prevents the small frequency adjustment from being made when correcting for an ADJ_OFFSET value.

       STA_PPSSIGNAL (read-only)
              A valid PPS (pulse-per-second) signal is present.

       STA_PPSJITTER (read-only)
              PPS signal jitter exceeded.

       STA_PPSWANDER (read-only)
              PPS signal wander exceeded.

       STA_PPSERROR (read-only)
              PPS signal calibration error.

       STA_CLOCKERR (read-only)
              Clock hardware fault.

       STA_NANO (read-only; since Linux 2.6.26)
              Resolution (0 = microsecond, 1 = nanoseconds).  Set via ADJ_NANO, cleared via ADJ_MICRO.

       STA_MODE (since Linux 2.6.26)
              Mode (0 = Phase Locked Loop, 1 = Frequency Locked Loop).

       STA_CLK (read-only; since Linux 2.6.26)
              Clock source (0 = A, 1 = B); currently unused.

       Attempts to set read-only status bits are silently ignored.

   clock_adjtime ()
       The clock_adjtime() system call (added in Linux 2.6.39) behaves like adjtimex() but takes an additional clk_id argument  to  specify
       the particular clock on which to act.

   ntp_adjtime ()
       The  ntp_adjtime()  library  function (described in the NTP "Kernel Application Program API", KAPI) is a more portable interface for
       performing the same task as adjtimex().  Other than the following points, it is identical to adjtimex():

       *  The constants used in modes are prefixed with "MOD_" rather than "ADJ_", and have the same suffixes (thus,  MOD_OFFSET,  MOD_FRE‐
          QUENCY, and so on), other than the exceptions noted in the following points.

       *  MOD_CLKA is the synonym for ADJ_OFFSET_SINGLESHOT.

       *  MOD_CLKB is the synonym for ADJ_TICK.

       *  The is no synonym for ADJ_OFFSET_SS_READ, which is not described in the KAPI.
        """
        ]
    # text = """"""
    for inum, text in enumerate(ls):
        print(inum)
        chunks = text_splitter.split_text(text)
        for chunk in chunks:
            print('length:', len(chunk), '\nchunk:',chunk)
            

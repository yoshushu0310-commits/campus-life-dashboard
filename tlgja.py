import os
import re
from collections import Counter
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib import font_manager, rc
from wordcloud import WordCloud
from konlpy.tag import Okt

# ---------------------------------------------------------
# 1. 폰트 설정 (스크립트 기준 NanumGothic 절대 경로 우선 탐색)
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
font_path = os.path.join(BASE_DIR, "NanumGothic.ttf")

if os.path.exists(font_path):
    font_manager.fontManager.addfont(font_path)
    font_prop = font_manager.FontProperties(fname=font_path)
    rc('font', family=font_prop.get_name())
else:
    # NanumGothic.ttf가 없을 경우 OS 기본 한글 폰트로 대체
    font_path = "C:/Windows/Fonts/malgun.ttf" if os.path.exists(
        "C:/Windows/Fonts/malgun.ttf") else "/System/Library/Fonts/Supplemental/AppleGothic.dfont"
    if os.path.exists(font_path):
        font_prop = font_manager.FontProperties(fname=font_path)
        rc('font', family=font_prop.get_name())

plt.rcParams['axes.unicode_minus'] = False  # 음수 부호 깨짐 방지

# ---------------------------------------------------------
# 2. 대폭 확장된 감성 어휘 사전 (기본형 기준: 명사, 형용사, 동사)
# ---------------------------------------------------------
POSITIVE_WORDS = {
    # 형용사 / 동사 어간
    '좋다', '만족스럽다', '뿌듯하다', '유익하다', '친절하다', '편하다', '편리하다',
    '깨끗하다', '즐겁다', '재미있다', '재밌다', '쾌적하다', '알차다', '훌륭하다',
    '체계적이다', '감사하다', '도움되다', '발전하다', '성장하다', '보람차다',
    # 명사
    '만족', '추천', '최고', '도움', '우수', '보람', '발전', '흥미', '열정', '칭찬',
    '장점', '호평', '기대', '사랑', '화이팅', '응원', '합격', '효과', '행복'
}

NEGATIVE_WORDS = {
    # 형용사 / 동사 어간
    '나쁘다', '불만족스럽다', '불편하다', '힘들다', '어렵다', '부족하다', '아쉽다',
    '지루하다', '답답하다', '귀찮다', '짜증나다', '복잡하다', '혼잡하다', '시끄럽다',
    '더럽다', '낙후되다', '부실하다', '과중하다', '지치다', '싫다',
    # 명사
    '불만', '부족', '불편', '아쉬움', '개선', '단점', '오류', '문제', '고통',
    '스트레스', '피곤', '지각', '비효율', '혼란', '지적', '부담', '낭비', '위험'
}

# ---------------------------------------------------------
# 3. 레이아웃 및 파일 업로드 UI
# ---------------------------------------------------------
st.set_page_config(page_title="부산대학교 학생회 데이터 분석", layout="wide")
st.title("🎓 부산대학교 학생회 학과별 설문 데이터 분석")

uploaded_file = st.file_uploader("📂 설문조사 CSV 파일을 업로드해주세요", type=["csv"])

if uploaded_file is not None:
    df_raw = pd.read_csv(uploaded_file)

    st.subheader("📋 데이터 미리보기")
    st.dataframe(df_raw.head())

    # ---------------------------------------------------------
    # 4. 결측치 및 이상치 전처리
    # ---------------------------------------------------------
    required_cols = ['학과', '만족도', '통학시간', '공부시간', '스마트폰', '한줄의견']
    missing_cols = [col for col in required_cols if col not in df_raw.columns]

    if missing_cols:
        st.error(f"CSV 파일에 필수 컬럼이 누락되었습니다: {missing_cols}")
        st.stop()

    initial_count = len(df_raw)
    df_clean = df_raw.dropna(subset=required_cols).copy()

    numeric_cols = ['만족도', '통학시간', '공부시간', '스마트폰']
    for col in numeric_cols:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

    df_clean = df_clean.dropna(subset=numeric_cols)
    for col in numeric_cols:
        df_clean = df_clean[df_clean[col] >= 0]

    dropped_count = initial_count - len(df_clean)
    st.info(f"ℹ️ 데이터 정제 완료: 잘못된/결측 데이터 총 **{dropped_count}건**을 분석에서 제외했습니다.")

    # ---------------------------------------------------------
    # 5. 학과 선택 필터 및 평균 만족도 (10점 만점 기준)
    # ---------------------------------------------------------
    dept_list = sorted(df_clean['학과'].unique().tolist())
    selected_dept = st.selectbox("📌 분석할 학과를 선택하세요:", dept_list)

    filtered_df = df_clean[df_clean['학과'] == selected_dept]

    # 평균 만족도 출력 (10.0점 만점 반영)
    avg_satisfaction = filtered_df['만족도'].mean()
    st.metric(label=f"⭐ {selected_dept} 평균 만족도", value=f"{avg_satisfaction:.2f}점 / 10.0점")

    # ---------------------------------------------------------
    # 6. 생활시간 원그래프 & 한줄의견 워드클라우드
    # ---------------------------------------------------------
    col1, col2 = st.columns(2)

    # [그래프 1] 생활시간 비율 원그래프 (통학시간: 분 -> 시간 환산)
    with col1:
        st.write("#### ⏳ 일일 생활시간 분포")

        avg_commute_min = filtered_df['통학시간'].mean()  # 원본 단위: 분
        avg_study_hr = filtered_df['공부시간'].mean()     # 원본 단위: 시간
        avg_phone_hr = filtered_df['스마트폰'].mean()     # 원본 단위: 시간

        avg_commute_hr = avg_commute_min / 60.0
        time_data = [avg_commute_hr, avg_study_hr, avg_phone_hr]
        time_labels = [
            f'통학시간 ({avg_commute_min:.0f}분 / {avg_commute_hr:.1f}시간)',
            f'공부시간 ({avg_study_hr:.1f}시간)',
            f'스마트폰 사용 ({avg_phone_hr:.1f}시간)'
        ]

        fig1, ax1 = plt.subplots(figsize=(6, 5))
        if sum(time_data) > 0:
            ax1.pie(
                time_data,
                labels=time_labels,
                autopct='%1.1f%%',
                startangle=90,
                colors=['#ff9999', '#66b3ff', '#99ff99']
            )
            ax1.set_title(f"[{selected_dept}] 학생 일일 생활시간 비율 (환산 단위: 시간)", fontsize=12)
        else:
            ax1.text(0.5, 0.5, "표시할 시간 데이터가 없습니다.", ha='center', va='center')
        st.pyplot(fig1)

    # [한줄의견 형태소 분석 및 감성 단어 추출]
    all_text = " ".join(filtered_df['한줄의견'].astype(str).tolist())
    clean_text = re.sub(r'[^가-힣\s]', ' ', all_text)

    okt = Okt()

    # 1) 워드클라우드 및 Top 10용: 명사(Noun) 추출
    nouns = okt.nouns(clean_text)
    filtered_nouns = [word for word in nouns if len(word) > 1]
    noun_counts = Counter(filtered_nouns)

    # 2) 감성 분석용: 명사, 형용사, 동사를 어간(stem=True)으로 추출
    pos_tagged = okt.pos(clean_text, stem=True)
    sentiment_candidates = [word for word, tag in pos_tagged if tag in ['Noun', 'Adjective', 'Verb'] and len(word) > 1]
    sentiment_counts = Counter(sentiment_candidates)

    # [그래프 2] 워드클라우드
    with col2:
        st.write("#### 💬 한줄의견 주요 키워드 클라우드")
        fig2, ax2 = plt.subplots(figsize=(6, 5))

        if filtered_nouns and os.path.exists(font_path):
            wordcloud = WordCloud(
                font_path=font_path,
                background_color='white',
                width=600,
                height=500,
                colormap='viridis'
            ).generate_from_frequencies(noun_counts)

            ax2.imshow(wordcloud, interpolation='bilinear')
            ax2.axis('off')
            ax2.set_title(f"[{selected_dept}] 한줄의견 워드클라우드 (단위: 빈도)", fontsize=12)
        else:
            ax2.text(0.5, 0.5, "표시할 키워드가 부족합니다.", ha='center', va='center')
            ax2.axis('off')
        st.pyplot(fig2)

    # ---------------------------------------------------------
    # 7. 한줄의견 막대그래프 (Top 10 키워드 & 긍정/부정 빈도)
    # ---------------------------------------------------------
    st.write("---")
    st.subheader(f"📊 [{selected_dept}] 한줄의견 상세 빈도 분석")

    col3, col4 = st.columns(2)

    # [그래프 3] 최다 언급 단어 Top 10 가로 막대그래프
    with col3:
        st.write("#### 🏆 최다 언급 단어 Top 10")
        fig3, ax3 = plt.subplots(figsize=(6, 5))

        top10 = noun_counts.most_common(10)
        if top10:
            words, counts = zip(*top10)
            ax3.barh(words[::-1], counts[::-1], color='#4C72B0')
            ax3.set_xlabel("등장 횟수 (단위: 건)", fontsize=11)
            ax3.set_ylabel("명사 키워드", fontsize=11)
            ax3.set_title(f"[{selected_dept}] 최다 언급 명사 Top 10", fontsize=12)

            for idx, count in enumerate(counts[::-1]):
                ax3.text(count + 0.1, idx, f"{count}건", va='center', fontsize=9)
        else:
            ax3.text(0.5, 0.5, "추출된 키워드가 없습니다.", ha='center', va='center')

        st.pyplot(fig3)

    # [그래프 4] 긍정 vs 부정 단어 출현 빈도 막대그래프
    with col4:
        st.write("#### ⚖️ 긍정 / 부정 단어 출현 빈도")

        pos_count = sum(sentiment_counts[word] for word in POSITIVE_WORDS if word in sentiment_counts)
        neg_count = sum(sentiment_counts[word] for word in NEGATIVE_WORDS if word in sentiment_counts)

        sentiment_labels = ['긍정 단어', '부정 단어']
        sentiment_values = [pos_count, neg_count]

        fig4, ax4 = plt.subplots(figsize=(6, 5))
        bars = ax4.bar(sentiment_labels, sentiment_values, color=['#55A868', '#C44E52'], width=0.5)
        ax4.set_ylabel("등장 횟수 (단위: 건)", fontsize=11)
        ax4.set_title(f"[{selected_dept}] 긍정 및 부정 단어 등장 건수 비교", fontsize=12)

        for bar in bars:
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width() / 2.0, height + 0.1, f"{int(height)}건", ha='center', va='bottom', fontsize=10)

        ax4.set_ylim(0, max(sentiment_values + [5]) * 1.2)
        st.pyplot(fig4)

else:
    st.write("분석을 시작하려면 상단에서 CSV 파일을 업로드해 주세요.")
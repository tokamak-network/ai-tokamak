#!/bin/bash
set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 결과 디렉토리 생성
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="evaluation_results_${TIMESTAMP}"
mkdir -p "${RESULTS_DIR}"

echo "${BLUE}=== 토카막 응답 평가 시스템 ===${NC}"
echo "결과 디렉토리: ${RESULTS_DIR}\n"

# Step 1: SYSTEM_PROMPT 생성
echo "${YELLOW}[1/4] SYSTEM_PROMPT 생성 중...${NC}"
tokamak show-system-prompt > "${RESULTS_DIR}/SYSTEM_PROMPT.md"
echo "${GREEN}✓ SYSTEM_PROMPT.md 생성 완료${NC}\n"

# Step 2: 질문 리스트 생성
echo "${YELLOW}[2/4] 평가용 질문 생성 중...${NC}"
claude --dangerously-skip-permissions -p "디스코드 AI 상담사를 테스트하기 위한 질문을 작성해야 합니다. @${RESULTS_DIR}/SYSTEM_PROMPT.md를 참고해서 질문 10개를 작성하세요. 한줄에 하나의 질문만 작성해야 하며, 질문 외에 다른 텍스트는 출력하지 마세요." --output-format text > "${RESULTS_DIR}/questions.txt"
echo "${GREEN}✓ 질문 생성 완료${NC}\n"

# Step 3: 각 질문에 대한 응답 생성 및 평가
echo "${YELLOW}[3/4] 응답 생성 및 평가 중...${NC}"
QUESTION_NUM=0
REPORT_FILE="${RESULTS_DIR}/evaluation_report.md"

# 리포트 헤더 작성
cat > "${REPORT_FILE}" << 'EOF'
# 토카막 AI 응답 평가 리포트

## 평가 기준
1. **디스코드 마크다운 호환성**: 디스코드에서 지원하지 않는 마크다운 문법(####, 등) 사용 여부
2. **번역 품질**: 오번역 또는 영어 대명사의 어색한 한국어 번역 여부
3. **정보 정확성**: 잘못된 정보 포함 여부
4. **한국어 자연스러움**: 한국어 사용자가 이해하기 쉬운 문장 구성

---

EOF

# Function to check if a line is a real question
is_valid_question() {
    local line="$1"

    # Skip if empty
    [ -z "$line" ] && return 1

    # Skip common meta-instruction patterns (case-insensitive)
    echo "$line" | grep -qiE "^(Looking at|I'll create|Here are|Based on|Below are|Following)" && return 1

    # Accept if it ends with Korean/English question marks or looks like a sentence
    echo "$line" | grep -qE "(\?|가요\?|나요\?|습니까\?|까요\?)$|^[가-힣a-zA-Z]" && return 0

    # Default: skip
    return 1
}

# 질문 파일을 한 줄씩 읽기
while IFS= read -r question; do
    # 빈 줄 건너뛰기
    if [ -z "$question" ]; then
        continue
    fi

    # Skip non-question lines
    if ! is_valid_question "$question"; then
        echo "${YELLOW}  건너뛰기: ${question}${NC}" >&2
        continue
    fi

    QUESTION_NUM=$((QUESTION_NUM + 1))
    echo "${BLUE}질문 ${QUESTION_NUM}: ${question}${NC}"

    # 응답 생성
    RESPONSE_FILE="${RESULTS_DIR}/response_${QUESTION_NUM}.txt"
    echo "  응답 생성 중..."

    # tokamak generate-response 실행하고 출력에서 응답 부분만 추출
    tokamak generate-response "${question}" > "${RESPONSE_FILE}.raw" 2>&1 || {
        echo "${RED}  ✗ 응답 생성 실패${NC}"
        echo "## 질문 ${QUESTION_NUM}" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        echo "**질문**: ${question}" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        echo "**응답**: (생성 실패)" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        echo "**점수**: N/A" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        echo "---" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        continue
    }

    # 구분선 사이의 응답만 추출
    sed -E -n '/^=+$/,/^=+$/p' "${RESPONSE_FILE}.raw" | sed '1d;$d' > "${RESPONSE_FILE}"

    RESPONSE=$(cat "${RESPONSE_FILE}")
    echo "${GREEN}  ✓ 응답 생성 완료${NC}"

    # 평가 프롬프트 생성
    EVAL_PROMPT_FILE="${RESULTS_DIR}/eval_prompt_${QUESTION_NUM}.md"
    cat > "${EVAL_PROMPT_FILE}" << EOF
# 응답 평가 요청

아래 내용을 바탕으로 AI 응답의 품질을 평가해주세요.

## 시스템 프롬프트
\`\`\`
$(cat "${RESULTS_DIR}/SYSTEM_PROMPT.md")
\`\`\`

## 질문
${question}

## 생성된 응답
${RESPONSE}

## 평가 기준 (각 항목별 세부 체크)
1. **디스코드 마크다운 호환성** (2.5점):
   - #### 같은 헤더 문법이 사용되었는가? (디스코드는 #를 지원하지 않음)
   - 디스코드에서 렌더링되지 않는 마크다운 문법이 있는가?

2. **번역 품질** (2.5점):
   - "그", "그녀", "그것" 같은 어색한 대명사 번역이 있는가?
   - 영어 문장 구조를 그대로 번역한 부자연스러운 표현이 있는가?

3. **정보 정확성** (2.5점):
   - 시스템 프롬프트에 명시된 정보와 일치하는가?
   - 잘못된 정보나 근거 없는 주장이 포함되어 있는가?

4. **한국어 자연스러움** (2.5점):
   - 한국어 사용자가 자연스럽게 이해할 수 있는 문장인가?
   - 전문 용어를 적절히 사용했는가?

## 응답 형식
다음 형식으로 정확히 응답해주세요:

점수: X.X/10

감점 사항:
- [항목명] (X점 감점): 구체적인 문제점

개선 아이디어:
- 구체적인 개선 방안 1
- 구체적인 개선 방안 2
EOF

    # Claude를 사용하여 평가 실행
    echo "  평가 중..."
    EVALUATION_FILE="${RESULTS_DIR}/evaluation_${QUESTION_NUM}.txt"

    claude --dangerously-skip-permissions -p "@${EVAL_PROMPT_FILE}" --output-format text > "${EVALUATION_FILE}" 2>&1 || {
        echo "${RED}  ✗ 평가 실패${NC}"
        echo "평가 실패" > "${EVALUATION_FILE}"
    }

    EVALUATION=$(cat "${EVALUATION_FILE}")
    echo "${GREEN}  ✓ 평가 완료${NC}\n"

    # 리포트에 추가
    cat >> "${REPORT_FILE}" << EOF
## 질문 ${QUESTION_NUM}

**질문**: ${question}

**응답**:
\`\`\`
${RESPONSE}
\`\`\`

**평가 결과**:
${EVALUATION}

---

EOF

done < "${RESULTS_DIR}/questions.txt"

# Step 4: 요약 통계 생성
echo "${YELLOW}[4/4] 요약 통계 생성 중...${NC}"

# 점수 추출 및 평균 계산
SCORES=$(grep -E "점수: [0-9]+\.[0-9]+/10" "${REPORT_FILE}" | sed -E 's/점수: ([0-9]+\.[0-9]+)\/10/\1/' || echo "")

if [ -n "$SCORES" ]; then
    AVG_SCORE=$(echo "$SCORES" | awk '{ sum += $1; count++ } END { if (count > 0) print sum/count; else print "N/A" }')

    cat >> "${REPORT_FILE}" << EOF

## 요약

- **총 질문 수**: ${QUESTION_NUM}
- **평균 점수**: ${AVG_SCORE}/10

### 점수 분포
EOF

    echo "$SCORES" | nl | sed 's/^/질문 /' >> "${REPORT_FILE}"
fi

echo "${GREEN}✓ 평가 완료!${NC}\n"

# 결과 출력
echo "${BLUE}=== 평가 결과 ===${NC}"
echo "리포트 파일: ${REPORT_FILE}"
echo "전체 결과: ${RESULTS_DIR}/"
echo ""
echo "${GREEN}평가가 완료되었습니다!${NC}"
echo "리포트 확인: ${YELLOW}cat ${REPORT_FILE}${NC}"

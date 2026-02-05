#!/bin/bash
set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create results directory
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="evaluation_results_${TIMESTAMP}"
mkdir -p "${RESULTS_DIR}"

echo "${BLUE}=== Tokamak Response Evaluation System ===${NC}"
echo "Results directory: ${RESULTS_DIR}\n"

# Step 1: Generate SYSTEM_PROMPT
echo "${YELLOW}[1/4] Generating SYSTEM_PROMPT...${NC}"
tokamak show-system-prompt > "${RESULTS_DIR}/SYSTEM_PROMPT.md"
echo "${GREEN}✓ SYSTEM_PROMPT.md generated${NC}\n"

# Step 2: Generate question list
echo "${YELLOW}[2/4] Generating evaluation questions...${NC}"
claude --dangerously-skip-permissions -p "You need to create test questions for a Discord AI assistant. Refer to @${RESULTS_DIR}/SYSTEM_PROMPT.md and write 10 questions. Write only one question per line, and do not output any text other than the questions." --output-format text > "${RESULTS_DIR}/questions.txt"
echo "${GREEN}✓ Questions generated${NC}\n"

# Step 3: Generate responses and evaluate each question
echo "${YELLOW}[3/4] Generating responses and evaluating...${NC}"
QUESTION_NUM=0
REPORT_FILE="${RESULTS_DIR}/evaluation_report.md"

# Write report header
cat > "${REPORT_FILE}" << 'EOF'
# Tokamak AI Response Evaluation Report

## Evaluation Criteria
1. **Discord Markdown Compatibility**: Use of unsupported markdown syntax (####, etc.) in Discord
2. **Translation Quality**: Mistranslations or awkward Korean translations of English pronouns
3. **Information Accuracy**: Inclusion of incorrect information
4. **Korean Naturalness**: Ease of understanding for Korean-speaking users

---

EOF

# Function to check if a line is a real question
is_valid_question() {
    local line="$1"

    # Skip if empty
    [ -z "$line" ] && return 1

    # Skip common meta-instruction patterns (case-insensitive)
    echo "$line" | grep -qiE "^(Looking at|I'll create|Here are|Based on|Below are|Following)" && return 1

    # Accept if it ends with question mark or looks like a sentence
    echo "$line" | grep -qE "\?$|^[a-zA-Z가-힣]" && return 0

    # Default: skip
    return 1
}

# Read questions line by line
while IFS= read -r question; do
    # Skip empty lines
    if [ -z "$question" ]; then
        continue
    fi

    # Skip non-question lines
    if ! is_valid_question "$question"; then
        echo "${YELLOW}  Skipping: ${question}${NC}" >&2
        continue
    fi

    QUESTION_NUM=$((QUESTION_NUM + 1))
    echo "${BLUE}Question ${QUESTION_NUM}: ${question}${NC}"

    # Generate response
    RESPONSE_FILE="${RESULTS_DIR}/response_${QUESTION_NUM}.txt"
    echo "  Generating response..."

    # Execute tokamak generate-response and extract response part from output
    tokamak generate-response "${question}" > "${RESPONSE_FILE}.raw" 2>&1 || {
        echo "${RED}  ✗ Response generation failed${NC}"
        echo "## Question ${QUESTION_NUM}" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        echo "**Question**: ${question}" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        echo "**Response**: (generation failed)" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        echo "**Score**: N/A" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        echo "---" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        continue
    }

    # Extract only the response between separator lines
    sed -E -n '/^=+$/,/^=+$/p' "${RESPONSE_FILE}.raw" | sed '1d;$d' > "${RESPONSE_FILE}"

    RESPONSE=$(cat "${RESPONSE_FILE}")
    echo "${GREEN}  ✓ Response generated${NC}"

    # Create evaluation prompt
    EVAL_PROMPT_FILE="${RESULTS_DIR}/eval_prompt_${QUESTION_NUM}.md"
    cat > "${EVAL_PROMPT_FILE}" << EOF
# Response Evaluation Request

Please evaluate the quality of the AI response based on the content below.

## System Prompt
\`\`\`
$(cat "${RESULTS_DIR}/SYSTEM_PROMPT.md")
\`\`\`

## Question
${question}

## Generated Response
${RESPONSE}

## Evaluation Criteria (Detailed checks for each item)
1. **Discord Markdown Compatibility** (2.5 points):
   - Are header syntaxes like #### used? (Discord does not support #)
   - Are there markdown syntaxes that don't render in Discord?

2. **Translation Quality** (2.5 points):
   - Are there awkward pronoun translations like "그", "그녀", "그것"?
   - Are there unnatural expressions that directly translate English sentence structures?

3. **Information Accuracy** (2.5 points):
   - Does it match the information specified in the system prompt?
   - Does it contain incorrect information or unfounded claims?

4. **Korean Naturalness** (2.5 points):
   - Can Korean-speaking users naturally understand the sentences?
   - Is technical terminology used appropriately?

## Response Format
Please respond in exactly this format:

Score: X.X/10

Deductions:
- [Category] (X points deducted): Specific issue

Improvement Ideas:
- Specific improvement suggestion 1
- Specific improvement suggestion 2
EOF

    # Execute evaluation using Claude
    echo "  Evaluating..."
    EVALUATION_FILE="${RESULTS_DIR}/evaluation_${QUESTION_NUM}.txt"

    claude --dangerously-skip-permissions -p "@${EVAL_PROMPT_FILE}" --output-format text > "${EVALUATION_FILE}" 2>&1 || {
        echo "${RED}  ✗ Evaluation failed${NC}"
        echo "Evaluation failed" > "${EVALUATION_FILE}"
    }

    EVALUATION=$(cat "${EVALUATION_FILE}")
    echo "${GREEN}  ✓ Evaluation complete${NC}\n"

    # Add to report
    cat >> "${REPORT_FILE}" << EOF
## Question ${QUESTION_NUM}

**Question**: ${question}

**Response**:
\`\`\`
${RESPONSE}
\`\`\`

**Evaluation Result**:
${EVALUATION}

---

EOF

done < "${RESULTS_DIR}/questions.txt"

# Step 4: Generate summary statistics
echo "${YELLOW}[4/4] Generating summary statistics...${NC}"

# Extract scores and calculate average
SCORES=$(grep -E "Score: [0-9]+\.[0-9]+/10" "${REPORT_FILE}" | sed -E 's/Score: ([0-9]+\.[0-9]+)\/10/\1/' || echo "")

if [ -n "$SCORES" ]; then
    AVG_SCORE=$(echo "$SCORES" | awk '{ sum += $1; count++ } END { if (count > 0) print sum/count; else print "N/A" }')

    cat >> "${REPORT_FILE}" << EOF

## Summary

- **Total Questions**: ${QUESTION_NUM}
- **Average Score**: ${AVG_SCORE}/10

### Score Distribution
EOF

    echo "$SCORES" | nl | sed 's/^/Question /' >> "${REPORT_FILE}"
fi

echo "${GREEN}✓ Evaluation complete!${NC}\n"

# Output results
echo "${BLUE}=== Evaluation Results ===${NC}"
echo "Report file: ${REPORT_FILE}"
echo "All results: ${RESULTS_DIR}/"
echo ""
echo "${GREEN}Evaluation completed!${NC}"
echo "View report: ${YELLOW}cat ${REPORT_FILE}${NC}"

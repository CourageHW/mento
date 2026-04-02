import streamlit as st
import fitz  # PyMuPDF
import re

# --- [PDF 데이터 추출 함수 (웹 전용으로 약간 수정)] ---
@st.cache_data # 웹에서 매번 로딩하지 않도록 캐싱 처리
def extract_quiz_from_pdf(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    
    full_text = re.sub(r'--- PAGE \d+ ---', '', full_text)
    blocks = full_text.split("문항 ")
    all_questions = []
    ans_map = {'①': 1, '②': 2, '③': 3, '④': 4, '1': 1, '2': 2, '3': 3, '4': 4}

    for block in blocks[1:]:
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        
        ans_idx = -1
        for i, line in enumerate(lines):
            if "정답" in line or "The following table" in line:
                ans_idx = i
                break
                
        if ans_idx == -1: continue
        
        q_and_opt_lines = lines[:ans_idx]
        ans_lines = lines[ans_idx:]
        
        if len(q_and_opt_lines) < 5: continue

        opt1_idx = -1
        for i, line in enumerate(q_and_opt_lines):
            if re.match(r'^[①1]\s|^①', line):
                opt1_idx = i; break
        if opt1_idx == -1:
            for i, line in enumerate(q_and_opt_lines):
                if re.match(r'^[②2]\s|^②', line):
                    opt1_idx = max(0, i - 1); break
        if opt1_idx == -1:
            for i, line in enumerate(q_and_opt_lines):
                if re.match(r'^[③3]\s|^③', line):
                    opt1_idx = max(0, i - 2); break
        if opt1_idx == -1:
            opt1_idx = max(0, len(q_and_opt_lines) - 4)

        q_lines = q_and_opt_lines[:opt1_idx]
        opt_lines_raw = q_and_opt_lines[opt1_idx:]

        clean_options = []
        if len(opt_lines_raw) == 4:
            for opt in opt_lines_raw:
                cleaned = re.sub(r'^([①②③④]|1\.|2\.|3\.|4\.|1\s|2\s|3\s|4\s|1|2|3|4)\s*', '', opt).strip()
                clean_options.append(cleaned if cleaned else opt)
        else:
            current_opt = ""
            for line in opt_lines_raw:
                if re.match(r'^([①②③④]|1\.|2\.|3\.|4\.|1\s|2\s|3\s|4\s)', line) or line in ["1","2","3","4","①","②","③","④"]:
                    if current_opt: clean_options.append(current_opt)
                    current_opt = re.sub(r'^([①②③④]|1\.|2\.|3\.|4\.|1\s|2\s|3\s|4\s)\s*', '', line).strip()
                else:
                    if current_opt: current_opt += " " + line
                    else: current_opt = line
            if current_opt: clean_options.append(current_opt)

        while len(clean_options) < 4: clean_options.append("보기 없음")
        clean_options = clean_options[:4]

        q_text = q_lines[0].split('.', 1)[-1].strip() if '.' in q_lines[0] else q_lines[0]
        code_lines = q_lines[1:]

        indent_level = 0
        current_func = ""
        formatted_code = ""

        for line in code_lines:
            line = line.replace('$', '').replace('~', ' ').strip()
            if not line: continue

            if line.startswith("def "):
                indent_level = 0
                parts = line[4:].split('(')
                if parts: current_func = parts[0].strip()

            if indent_level > 0 and current_func:
                if (current_func + "(" in line) and not line.startswith("return"):
                    indent_level = 0

            if any(line.startswith(x) for x in ["else:", "elif ", "else"]):
                indent_level = max(0, indent_level - 1)

            spaced_line = ("    " * indent_level) + line
            formatted_code += "\n" + spaced_line

            if line.endswith(":") or line.startswith("if ") or line.startswith("elif ") or line.startswith("else") or line.startswith("for ") or line.startswith("while ") or line.startswith("def "):
                indent_level += 1

            if line in ["break", "continue", "pass"]:
                indent_level = max(0, indent_level - 1)
            elif line.startswith("return"):
                if line.strip() != "return": 
                    indent_level = max(0, indent_level - 1)

        final_q_text = q_text + "\n" + formatted_code

        correct_ans = 0
        for ans_line in ans_lines[:15]:
            ans_match = re.search(r'[①②③④]', ans_line)
            if ans_match:
                correct_ans = ans_map.get(ans_match.group(), 0)
                break
            
        all_questions.append({
            "q": final_q_text.strip(),
            "o": clean_options,
            "a": correct_ans if correct_ans != 0 else 1 
        })

    return all_questions

# --- [상태 초기화 및 웹 UI] ---
st.set_page_config(page_title="파이썬 마스터 200", page_icon="🚀", layout="centered")

if 'idx' not in st.session_state:
    st.session_state.idx = 0
    st.session_state.wrong_pool = []
    st.session_state.current_pool = []
    st.session_state.all_questions = []
    st.session_state.round_ended = False
    st.session_state.mission_complete = False

st.title("🚀 파이썬 마스터 200")
st.markdown("**오답 무한 반복 시스템** (멘티용 웹버전)")

# PDF 자동 로드 (깃허브에 올라간 파일 사용)
if not st.session_state.all_questions:
    with st.spinner("🚀 문제를 불러오는 중입니다... 잠시만 기다려주세요!"):
        try:
            # 깃허브에 올라간 PDF 파일명과 정확히 똑같아야 합니다.
            with open("파이썬_객관식_200문항.pdf", "rb") as f:
                pdf_bytes = f.read()
            
            questions = extract_quiz_from_pdf(pdf_bytes)
            
            if questions:
                st.session_state.all_questions = questions
                st.session_state.current_pool = questions[:]
                st.rerun()
            else:
                st.error("문제를 불러오지 못했습니다. PDF 파일 형식을 확인해주세요.")
        except FileNotFoundError:
            st.error("⚠️ '파이썬_객관식_200문항.pdf' 파일을 찾을 수 없습니다. 깃허브 저장소에 파일이 잘 올라가 있는지 확인해주세요!")

else:
    # 모든 문제 정복 시
    if st.session_state.mission_complete:
        st.balloons()
        st.success("🎉 축하합니다! 200문제를 모두 마스터했습니다!")
        if st.button("처음부터 다시 시작하기", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # 한 라운드 끝났을 때
    elif st.session_state.round_ended:
        st.warning(f"이번 라운드 종료! 틀린 문제 {len(st.session_state.wrong_pool)}개를 다시 풉니다.")
        if st.button("오답 격파 시작하기", use_container_width=True, type="primary"):
            st.session_state.current_pool = st.session_state.wrong_pool[:]
            st.session_state.wrong_pool = []
            st.session_state.idx = 0
            st.session_state.round_ended = False
            st.rerun()

    # 문제 푸는 중일 때
    elif st.session_state.current_pool:
        idx = st.session_state.idx
        pool_size = len(st.session_state.current_pool)
        
        st.progress(idx / pool_size, text=f"진행도: {idx + 1} / {pool_size}")
        current_q = st.session_state.current_pool[idx]
        
        q_text_split = current_q['q'].split('\n', 1)
        st.subheader(f"Q. {q_text_split[0]}")
        if len(q_text_split) > 1:
            st.code(q_text_split[1], language="python")

        # 폼을 사용하여 엔터키 지원 및 화면 깜빡임 방지
        with st.form(key=f"quiz_form_{idx}"):
            user_choice = st.radio("정답을 선택하세요:", current_q['o'], index=None)
            submit_button = st.form_submit_button(label='확인 (제출)', use_container_width=True)
            
            if submit_button:
                if user_choice is None:
                    st.error("보기를 선택해주세요!")
                else:
                    selected_idx = current_q['o'].index(user_choice) + 1
                    
                    if selected_idx != current_q['a']:
                        st.session_state.wrong_pool.append(current_q)
                    
                    st.session_state.idx += 1
                    
                    if st.session_state.idx >= len(st.session_state.current_pool):
                        if len(st.session_state.wrong_pool) > 0:
                            st.session_state.round_ended = True
                        else:
                            st.session_state.mission_complete = True
                    
                    st.rerun()

"""Prompt text: grading a guided-question answer, and the homework tutor prompt."""

GRADER_SYSTEM = """You grade short written answers for a self-taught student taking {course}.
Be strict, like a demanding teacher in person.

Rules:
- Judge only whether the answer shows real understanding of the question, using the reference points.
- A vague, partly wrong, or memorized-sounding answer is NOT YET. When in doubt, NOT YET.
- No praise, no encouragement, no softening. State what is right, what is missing or wrong, and stop.
- End with one follow-up question that tests the same idea from a different angle.
- Reply in {lang_name}.

Format exactly:
VERDICT: PASS or VERDICT: NOT YET
Then at most 5 short lines of feedback.
Then a line starting "Follow-up:" with the question."""

GRADER_USER = """Question: {question}

Reference points (from the lecture; the student has not seen this list):
{points}

Student's answer:
{answer}"""


def grader(course_name, question, points, answer, lang):
    system = GRADER_SYSTEM.format(course=course_name, lang_name="Chinese" if lang == "zh" else "English")
    user = GRADER_USER.format(question=question, answer=answer.strip(),
                              points="\n".join("- " + p for p in points) or "- (none)")
    return system, user


def parse_verdict(text):
    first = text.strip().splitlines()[0].upper() if text.strip() else ""
    if "NOT YET" in first:
        return "not_yet"
    if "PASS" in first:
        return "pass"
    return None


def grader_copy_prompt(course_name, question, points, answer, lang):
    """Same grading as one paste-able block, for people with no key set."""
    system, user = grader(course_name, question, points, answer, lang)
    return system + "\n\n---\n\n" + user


HW = {
    "en": {
        "intro": "You are my homework tutor.",
        "course": "Course: {course} · {name}",
        "files": "My files: {path}",
        "hints": "1. While I work: hints only, no full code.",
        "hints_written": "1. While I work: hints only, no answers.",
        "done_prog": "2. When I say \"done\": read {starter}, run the tests. Tests decide right or wrong; you only explain. If {tests} does not exist yet, write it from the instructions ({spec}) first and list which cases I should check by hand. Do not put solutions in it.",
        "done_written": "2. When I say \"done\": I will paste my answers. Check each against the instructions ({spec}). Point to the exact step that is wrong; do not give the answer.",
        "quiz": "3. Quiz me on: {concepts}.",
        "angles": "4. 2+ angles per concept. Wrong = not passed; retest from a new angle.",
        "output": "5. Output: pass/fail per concept + my stuck points.",
        "stuck": "Stuck so far: {items}.",
        "tone": "No praise unless it names a concrete improvement.",
    },
    "zh": {
        "intro": "你是我的作业辅导老师。",
        "course": "课程：{course} · {name}",
        "files": "我的文件：{path}",
        "hints": "1. 我做题时：只给提示，不给完整代码。",
        "hints_written": "1. 我做题时：只给提示，不给答案。",
        "done_prog": "2. 我说“写完了”：读 {starter}，跑测试。对错由测试决定，你只负责解释。如果还没有 {tests}，先按作业说明（{spec}）写一个，并列出需要我手动核对的用例。测试里不要放答案。",
        "done_written": "2. 我说“写完了”：我会贴上答案。逐题对照作业说明（{spec}）检查，指出错在哪一步，不直接给答案。",
        "quiz": "3. 考我：{concepts}。",
        "angles": "4. 每个概念至少 2 个角度。答错即不过，换角度重考。",
        "output": "5. 输出：每个概念 过/不过 + 我的卡点。",
        "stuck": "目前的卡点：{items}。",
        "tone": "不要空洞表扬；要夸就指出具体进步。",
    },
}


def homework_prompt(course, assignment, lang, workspace_path, stuck_items):
    t = HW["zh" if lang == "zh" else "en"]
    sep = "；" if lang == "zh" else "; "
    concepts = sep.join(c["zh" if lang == "zh" else "en"] for c in assignment["concepts"])
    spec_files = [m["label"] for m in assignment["materials"] if not m.get("starter")]
    starter = next((m["label"] for m in assignment["materials"] if m.get("starter")), None)
    lines = [t["intro"], t["course"].format(course="CMU " + course["code"], name=assignment["name"]),
             t["files"].format(path=workspace_path), "",
             t["hints"] if assignment.get("kind") == "programming" else t["hints_written"]]
    if assignment.get("kind") == "programming" and starter:
        tests = "test_" + starter
        lines.append(t["done_prog"].format(starter=starter, tests=tests, spec=", ".join(spec_files)))
    else:
        lines.append(t["done_written"].format(spec=", ".join(spec_files)))
    lines += [t["quiz"].format(concepts=concepts), t["angles"], t["output"]]
    if stuck_items:
        lines += ["", t["stuck"].format(items=sep.join(stuck_items))]
    lines += [t["tone"]]
    return "\n".join(lines)

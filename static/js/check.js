// 获取元素
const questionEl = document.getElementById('question');
const inputArea = document.getElementById('input-area');
const submitBtn = document.getElementById('submit-btn');
const resultEl = document.getElementById('result');
const wordEn = document.getElementById('word-en').value;
const wordZh = document.getElementById('word-zh').value;
const listName = document.getElementById('list-name').value;
let currentMode = 'en2zh'; // 默认

// 按钮事件
document.getElementById('btn-en2zh').addEventListener('click', () => setMode('en2zh'));
document.getElementById('btn-zh2en').addEventListener('click', () => setMode('zh2en'));

function setMode(mode) {
    currentMode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
    if (mode === 'en2zh') {
        document.getElementById('btn-en2zh').classList.add('active');
        questionEl.textContent = wordEn;
    } else {
        document.getElementById('btn-zh2en').classList.add('active');
        questionEl.textContent = wordZh;
    }
    createInputArea(mode);
    resultEl.innerHTML = '';
}

function createInputArea(mode) {
    inputArea.innerHTML = '';
    if (mode === 'en2zh') {
        // 普通文本框
        const input = document.createElement('input');
        input.type = 'text';
        input.id = 'answer-input';
        input.placeholder = '输入中文意思';
        inputArea.appendChild(input);
    } else {
        // 字母格子
        const word = wordEn;
        for (let i = 0; i < word.length; i++) {
            const box = document.createElement('input');
            box.type = 'text';
            box.maxLength = 1;
            box.className = 'letter-box';
            box.dataset.index = i;
            box.addEventListener('input', handleInput);
            box.addEventListener('keydown', handleKeyDown);
            inputArea.appendChild(box);
        }
        if (inputArea.firstChild) inputArea.firstChild.focus();
    }
}

function handleInput(e) {
    const input = e.target;
    if (input.value.length === 1) {
        const next = input.nextElementSibling;
        if (next) next.focus();
    }
}

function handleKeyDown(e) {
    if (e.key === 'Backspace') {
        const input = e.target;
        if (input.value === '' && input.previousElementSibling) {
            input.previousElementSibling.focus();
        }
    }
}

// 提交答案
submitBtn.addEventListener('click', () => {
    let answer;
    if (currentMode === 'en2zh') {
        answer = document.getElementById('answer-input')?.value || '';
    } else {
        const boxes = document.querySelectorAll('.letter-box');
        answer = Array.from(boxes).map(b => b.value).join('');
    }

    fetch('/check/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            mode: currentMode,
            answer: answer,
            word_en: wordEn,
            word_zh: wordZh,
            list_name: listName
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.correct) {
            resultEl.innerHTML = '<p class="correct">✓ 回答正确！</p>';
        } else {
            resultEl.innerHTML = `<p class="incorrect">✗ 回答错误。正确答案是：${data.expected}</p>`;
        }
        // 可选项：自动切换到下一个单词（需刷新页面或重新加载，为简化，手动刷新）
        // 这里我们简单提示后可以刷新页面
        setTimeout(() => {
            if (confirm('是否继续下一个单词？')) {
                location.reload();
            }
        }, 1000);
    });
});

// 初始化
setMode('en2zh');

/**
 * 编辑笔记页面AJAX处理
 * 实现无刷新保存笔记
 */

document.addEventListener('DOMContentLoaded', function() {
    const editForm = document.querySelector('form[action^="/edit_note/"]');
    if (!editForm) return;

    const csrfTokenInput = editForm.querySelector('input[name="csrf_token"]');
    const metaTokenEl = document.querySelector('meta[name="csrf-token"]');
    const csrfToken =
        window.CSRF_TOKEN ||
        (metaTokenEl ? metaTokenEl.getAttribute('content') : null) ||
        (csrfTokenInput ? csrfTokenInput.value : null);

    // 添加ID到表单
    editForm.id = 'editNoteForm';

    // 获取noteId
    const noteId = editForm.action.split('/').pop();

    // 获取保存按钮
    const saveBtn = editForm.querySelector('button[type="submit"]');
    if (!saveBtn) return;

    // 添加ID到按钮文本
    const saveBtnTextEl = saveBtn.querySelector('svg').nextSibling;
    if (saveBtnTextEl && saveBtnTextEl.nodeType === Node.TEXT_NODE) {
        const span = document.createElement('span');
        span.id = 'saveBtnText';
        span.textContent = saveBtnTextEl.textContent.trim();
        saveBtnTextEl.replaceWith(span);
    }

    editForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const saveBtnText = document.getElementById('saveBtnText');
        const newText = document.getElementById('message_text').value.trim();

        // 禁用按钮
        saveBtn.disabled = true;
        const originalText = saveBtnText ? saveBtnText.textContent : '保存修改';
        if (saveBtnText) saveBtnText.textContent = '保存中...';

        const headers = { 'Content-Type': 'application/json' };
        if (csrfToken) headers['X-CSRFToken'] = csrfToken;

        fetch(`/api/edit_note/${noteId}`, {
            method: 'POST',
            headers,
            body: JSON.stringify({ message_text: newText })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 成功提示
                if (saveBtnText) saveBtnText.textContent = '保存成功!';
                setTimeout(() => {
                    // 返回上一页
                    window.history.back();
                }, 500);
            } else {
                throw new Error(data.error || '更新失败');
            }
        })
        .catch(error => {
            console.error('更新笔记失败:', error);
            alert('更新失败: ' + error.message);
            saveBtn.disabled = false;
            if (saveBtnText) saveBtnText.textContent = originalText;
        });
    });
});

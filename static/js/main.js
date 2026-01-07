// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // AI标签切换
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.ai-tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // 移除所有激活状态
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // 添加当前激活状态
            this.classList.add('active');
            const tabId = this.getAttribute('data-tab') + '-tab';
            document.getElementById(tabId).classList.add('active');
        });
    });

    // 书法字典详情查看（简易版）
    window.viewDetail = function(id) {
        alert('字帖ID：' + id + '，完整详情功能可根据课设需求扩展');
    };
});
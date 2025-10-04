// 导航栏组件
const NavBar = {
    name: 'NavBar',
    props: {
        activePage: {
            type: String,
            default: 'dashboard'
        }
    },
    template: `
        <div class="navbar">
            <div class="navbar-content">
                <div class="navbar-left">
                    <div class="logo">
                        <span class="logo-icon">👑</span>
                        <span class="logo-text">哈基米</span>
                    </div>
                    <div class="nav">
                        <a href="/" :class="{ active: activePage === 'dashboard' }">📊 仪表盘</a>
                        <a href="/keys" :class="{ active: activePage === 'keys' }">🔑 密钥管理</a>
                        <a href="/stats" :class="{ active: activePage === 'stats' }">📈 统计分析</a>
                        <a href="/providers" :class="{ active: activePage === 'providers' }">🤖 AI供应商</a>
                        <a href="/config" :class="{ active: activePage === 'config' }">⚙️ 系统配置</a>
                    </div>
                </div>
                <div class="navbar-right">
                    <el-button type="danger" size="small" @click="handleLogout">退出登录</el-button>
                </div>
            </div>
        </div>
    `,
    methods: {
        handleLogout() {
            localStorage.removeItem('access_token');
            window.location.href = '/login';
        }
    }
};

// 导航栏样式
const navbarStyles = `
.navbar {
    background: #fff;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    padding: 16px 0;
    position: sticky;
    top: 0;
    z-index: 100;
}

.navbar-content {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.navbar-left {
    display: flex;
    align-items: center;
    gap: 2rem;
}

.navbar-right {
    margin-left: auto;
}

.logo {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 24px;
    font-weight: bold;
    cursor: pointer;
}

.logo-icon {
    font-size: 32px;
    line-height: 1;
    filter: none !important;
}

.logo-text {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.nav {
    display: flex;
    gap: 20px;
}

.nav a {
    text-decoration: none;
    color: #606266;
    font-weight: 500;
    transition: color 0.3s;
    padding: 8px 12px;
    border-radius: 4px;
}

.nav a:hover {
    color: #409eff;
    background: rgba(64, 158, 255, 0.1);
}

.nav a.active {
    color: #409eff;
    background: rgba(64, 158, 255, 0.15);
}
`;

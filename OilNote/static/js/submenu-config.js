// 공통 서브메뉴 설정 및 함수들
const SUBMENU_CONFIG = {
    'basic-data': {
        title: '기초자료',
        items: [
            {
                text: '주유소 사업자 등록',
                icon: 'fas fa-building',
                href: '/stations-manage/business-registration/'
            },
            {
                text: '유종 및 유외상품 등록',
                icon: 'fas fa-gas-pump',
                href: '/stations-manage/product-registration/'
            },
            {
                text: '탱크 정보 등록',
                icon: 'fas fa-cube',
                href: '/stations-manage/tank-registration/'
            },
            {
                text: '주유기 노즐 정보 등록',
                icon: 'fas fa-tint',
                href: '/stations-manage/nozzle-registration/'
            },
            {
                text: '홈로리 차량 등록',
                icon: 'fas fa-truck',
                href: '/stations-manage/homelori-registration/'
            },
            {
                text: '결제 형태 등록',
                icon: 'fas fa-credit-card',
                href: '/stations-manage/payment-registration/'
            },
            {
                text: '기초 자료(값) 등록',
                icon: 'fas fa-database',
                href: '#',
                submenu: [
                    {
                        text: '탱크 기초재고',
                        icon: 'fas fa-cube',
                        href: '/stations-manage/tank-inventory/'
                    },
                    {
                        text: '주유기 기초 계기자료',
                        icon: 'fas fa-tachometer-alt',
                        href: '/stations-manage/dispenser-meter/'
                    },
                    {
                        text: '유외상품 기초재고',
                        icon: 'fas fa-boxes',
                        href: '/stations-manage/product-inventory/'
                    },
                    {
                        text: '외상채권 기초잔액',
                        icon: 'fas fa-hand-holding-usd',
                        href: '/stations-manage/receivables/'
                    }
                ]
            }
        ]
    },
    'customer-management': {
        title: '거래처관리',
        items: [
            {
                text: '거래처 등록 및 수정',
                icon: 'fas fa-user-edit',
                href: '/stations-manage/customer-registration/'
            },
            {
                text: '차량 / 외상카드 등록',
                icon: 'fas fa-credit-card',
                href: '/stations-manage/vehicle-credit-registration/'
            }
        ]
    },
            'price-management': {
            title: '단가관리',
            items: [
                {
                    text: '기준 단가 입력',
                    icon: 'fas fa-dollar-sign',
                    href: '/stations-manage/standard-price/'
                },
                {
                    text: '할인 단가 설정',
                    icon: 'fas fa-percentage',
                    href: '/stations-manage/discount-price/'
                }
            ]
        }
};

// 공통 메뉴 열기 함수들
function openBasicDataMenu() {
    openSubmenuPopup('basic-data', '기초자료');
}

function openCustomerManagementMenu() {
    openSubmenuPopup('customer-management', '거래처관리');
}

function openPriceManagementMenu() {
    openSubmenuPopup('price-management', '단가관리');
}

// 공통 서브메뉴 플로팅 팝업 열기 함수
function openSubmenuPopup(menuType, title) {
    const submenuPopup = document.getElementById('submenuPopup');
    const submenuTitle = document.getElementById('submenuTitle');
    const submenuContent = document.getElementById('submenuContent');
    const mainContent = document.getElementById('mainContent');
    
    if (!submenuPopup || !submenuTitle || !submenuContent || !mainContent) {
        console.error('서브메뉴 요소를 찾을 수 없습니다.');
        return;
    }
    
    // 제목 설정
    submenuTitle.textContent = title;
    
    // 메뉴 아이템 생성
    const menuItems = SUBMENU_CONFIG[menuType].items;
    submenuContent.innerHTML = '';
    
    menuItems.forEach(item => {
        const link = document.createElement('a');
        link.href = item.href;
        link.className = 'submenu-popup-link';
        
        // 현재 페이지인 경우 active 클래스 추가
        if (item.href === window.location.pathname) {
            link.classList.add('active');
        }
        
        link.innerHTML = `
            <i class="${item.icon}"></i>
            <span class="menu-text">${item.text}</span>
        `;
        
        // 클릭 이벤트
        link.addEventListener('click', function(e) {
            if (item.href === '#') {
                e.preventDefault();
                console.log('메뉴 클릭:', item.text);
                
                // 서브메뉴가 있는 경우 처리
                if (item.submenu) {
                    showSubSubmenu(item.submenu, item.text);
                }
            } else {
                console.log('페이지 이동:', item.href);
                // 실제 링크인 경우 서브메뉴 닫기
                closeSubmenuPopup();
            }
        });
        
        submenuContent.appendChild(link);
    });
    
    // 팝업 열기
    submenuPopup.classList.add('show');
    if (mainContent) {
        mainContent.classList.add('submenu-open');
    }
}

// 공통 서브메뉴 플로팅 팝업 닫기 함수
function closeSubmenuPopup() {
    const submenuPopup = document.getElementById('submenuPopup');
    const mainContent = document.getElementById('mainContent');
    
    if (submenuPopup) {
        submenuPopup.classList.remove('show');
    }
    if (mainContent) {
        mainContent.classList.remove('submenu-open');
    }
}

// 공통 서브서브메뉴 표시 함수
function showSubSubmenu(submenuItems, parentTitle) {
    const submenuPopup = document.getElementById('submenuPopup');
    const submenuTitle = document.getElementById('submenuTitle');
    const submenuContent = document.getElementById('submenuContent');
    
    if (!submenuPopup || !submenuTitle || !submenuContent) {
        console.error('서브메뉴 요소를 찾을 수 없습니다.');
        return;
    }
    
    // 제목 설정 (부모 메뉴명 + 서브메뉴)
    submenuTitle.innerHTML = `
        <i class="fas fa-arrow-left me-2" style="cursor: pointer;" onclick="showMainSubmenu()"></i>
        ${parentTitle}
    `;
    
    // 서브서브메뉴 아이템 생성
    submenuContent.innerHTML = '';
    
    submenuItems.forEach(item => {
        const link = document.createElement('a');
        link.href = item.href;
        link.className = 'submenu-popup-link';
        
        // 현재 페이지인 경우 active 클래스 추가
        if (item.href === window.location.pathname) {
            link.classList.add('active');
        }
        
        link.innerHTML = `
            <i class="${item.icon}"></i>
            <span class="menu-text">${item.text}</span>
        `;
        
        // 클릭 이벤트
        link.addEventListener('click', function(e) {
            if (item.href === '#') {
                e.preventDefault();
                console.log('서브메뉴 클릭:', item.text);
            } else {
                console.log('페이지 이동:', item.href);
                // 실제 링크인 경우 서브메뉴 닫기
                closeSubmenuPopup();
            }
        });
        
        submenuContent.appendChild(link);
    });
    
    // 팝업 표시
    submenuPopup.classList.add('show');
}

// 공통 메인 서브메뉴로 돌아가기 함수
function showMainSubmenu() {
    const submenuPopup = document.getElementById('submenuPopup');
    const submenuTitle = document.getElementById('submenuTitle');
    const submenuContent = document.getElementById('submenuContent');
    
    if (!submenuPopup || !submenuTitle || !submenuContent) {
        console.error('서브메뉴 요소를 찾을 수 없습니다.');
        return;
    }
    
    // 제목을 원래대로 복원
    submenuTitle.innerHTML = `
        기초자료
        <button class="submenu-close-btn" id="submenuCloseBtn">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // 기존 서브메뉴 아이템들 다시 생성
    const menuItems = SUBMENU_CONFIG['basic-data'].items;
    submenuContent.innerHTML = '';
    
    menuItems.forEach(item => {
        const link = document.createElement('a');
        link.href = item.href;
        link.className = 'submenu-popup-link';
        
        // 현재 페이지인 경우 active 클래스 추가
        if (item.href === window.location.pathname) {
            link.classList.add('active');
        }
        
        link.innerHTML = `
            <i class="${item.icon}"></i>
            <span class="menu-text">${item.text}</span>
        `;
        
        // 클릭 이벤트
        link.addEventListener('click', function(e) {
            if (item.href === '#') {
                e.preventDefault();
                console.log('메뉴 클릭:', item.text);
                
                // 서브메뉴가 있는 경우 처리
                if (item.submenu) {
                    showSubSubmenu(item.submenu, item.text);
                }
            } else {
                console.log('페이지 이동:', item.href);
                // 실제 링크인 경우 서브메뉴 닫기
                closeSubmenuPopup();
            }
        });
        
        submenuContent.appendChild(link);
    });
    
    // 닫기 버튼 이벤트 다시 등록
    const closeBtn = document.getElementById('submenuCloseBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            closeSubmenuPopup();
        });
    }
}

// 서브메뉴 닫기 버튼 이벤트 등록
document.addEventListener('DOMContentLoaded', function() {
    const closeBtn = document.getElementById('submenuCloseBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            closeSubmenuPopup();
        });
    }
}); 
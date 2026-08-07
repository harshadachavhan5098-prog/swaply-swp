// Swaply Main JavaScript

// Mobile menu toggle
function toggleMobileMenu() {
    const navLinks = document.querySelector('.nav-links');
    if (navLinks) {
        navLinks.classList.toggle('show');
    }
}

// Close mobile menu when clicking outside
document.addEventListener('click', function (e) {
    const navLinks = document.querySelector('.nav-links');
    const navToggle = document.querySelector('.nav-toggle');
    if (navLinks && navLinks.classList.contains('show') && !navLinks.contains(e.target) && !navToggle.contains(e.target)) {
        navLinks.classList.remove('show');
    }
});

// Like button functionality
document.addEventListener('click', function (e) {
    const likeBtn = e.target.closest('.like-btn');
    if (likeBtn) {
        e.preventDefault();
        const postId = likeBtn.dataset.postId;
        if (!postId) return;

        fetch(`/post/${postId}/like`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            const countSpan = likeBtn.querySelector('.like-count');
            if (countSpan) {
                countSpan.textContent = data.count;
            }
            if (data.liked) {
                likeBtn.classList.add('liked');
            } else {
                likeBtn.classList.remove('liked');
            }
        })
        .catch(error => console.error('Error liking post:', error));
    }
});

// Comment toggle
document.addEventListener('click', function (e) {
    const toggleBtn = e.target.closest('.comment-toggle');
    if (toggleBtn) {
        const targetId = toggleBtn.dataset.target;
        if (targetId) {
            const commentsDiv = document.getElementById(targetId);
            if (commentsDiv) {
                commentsDiv.classList.toggle('show');
            }
        }
    }
});

// Auto-dismiss flash messages
document.addEventListener('DOMContentLoaded', function () {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function (msg) {
        setTimeout(function () {
            msg.style.opacity = '0';
            msg.style.transform = 'translateX(100%)';
            setTimeout(function () {
                msg.remove();
            }, 300);
        }, 5000);
    });
});

// Modal close on outside click
document.addEventListener('click', function (e) {
    if (e.target.classList.contains('modal')) {
        e.target.style.display = 'none';
    }
});

// Close modal with Escape key
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal').forEach(function (modal) {
            modal.style.display = 'none';
        });
    }
});

// File upload preview
document.addEventListener('change', function (e) {
    if (e.target.type === 'file' && e.target.closest('.file-upload')) {
        const label = e.target.closest('.file-upload');
        if (e.target.files.length > 0) {
            label.innerHTML = '<i class="fas fa-check"></i> ' + e.target.files[0].name;
        } else {
            label.innerHTML = '<i class="fas fa-image"></i> Add Image';
        }
    }
});

// Active nav link highlighting
document.addEventListener('DOMContentLoaded', function () {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(function (link) {
        const href = link.getAttribute('href');
        if (href && href !== '/' && currentPath.startsWith(href)) {
            link.classList.add('active');
        }
    });
});
function togglePassword5() {
    const passwordInput = document.getElementById("new-password");
    const toggleIcon = document.getElementById("toggleIcon5");

    if (passwordInput.type === "password") {
    passwordInput.type = "text";
    toggleIcon.classList.remove("fa-eye");
    toggleIcon.classList.add("fa-eye-slash");
    } else {
    passwordInput.type = "password";
    toggleIcon.classList.remove("fa-eye-slash");
    toggleIcon.classList.add("fa-eye");
    }
}

function togglePassword4() {
    const passwordInput = document.getElementById("confirm-password");
    const toggleIcon = document.getElementById("toggleIcon4");

    if (passwordInput.type === "password") {
    passwordInput.type = "text";
    toggleIcon.classList.remove("fa-eye");
    toggleIcon.classList.add("fa-eye-slash");
    } else {
    passwordInput.type = "password";
    toggleIcon.classList.remove("fa-eye-slash");
    toggleIcon.classList.add("fa-eye");
    }
}

function togglePassword3() {
    const passwordInput = document.getElementById("passwordInput3");
    const toggleIcon = document.getElementById("toggleIcon3");

    if (passwordInput.type === "password") {
    passwordInput.type = "text";
    toggleIcon.classList.remove("fa-eye");
    toggleIcon.classList.add("fa-eye-slash");
    } else {
    passwordInput.type = "password";
    toggleIcon.classList.remove("fa-eye-slash");
    toggleIcon.classList.add("fa-eye");
    }
}

function togglePassword2() {
    const passwordInput = document.getElementById("passwordInput2");
    const toggleIcon = document.getElementById("toggleIcon2");

    if (passwordInput.type === "password") {
    passwordInput.type = "text";
    toggleIcon.classList.remove("fa-eye");
    toggleIcon.classList.add("fa-eye-slash");
    } else {
    passwordInput.type = "password";
    toggleIcon.classList.remove("fa-eye-slash");
    toggleIcon.classList.add("fa-eye");
    }
}

function togglePassword() {
    const passwordInput = document.getElementById("passwordInput");
    const toggleIcon = document.getElementById("toggleIcon");

    if (passwordInput.type === "password") {
    passwordInput.type = "text";
    toggleIcon.classList.remove("fa-eye");
    toggleIcon.classList.add("fa-eye-slash");
    } else {
    passwordInput.type = "password";
    toggleIcon.classList.remove("fa-eye-slash");
    toggleIcon.classList.add("fa-eye");
    }
}

function handleFormSubmission(formId, responseDivId) {
    const form = document.getElementById(formId);
    const responseDiv = document.getElementById(responseDivId);

    if (!form) return;

    form.addEventListener('submit', async function (e) {
        e.preventDefault();

        const formData = new FormData(form);

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData,
                redirect: 'follow'
            });

            if (response.redirected || response.status === 0 || response.type === 'opaqueredirect') {
                window.location.href = response.url || '/';
                return;
            }

            const data = await response.json();

            responseDiv.textContent = data.message;
            responseDiv.style.color = data.status === 'success' ? 'green' : 'red';
            responseDiv.style.display = 'block';

            if (data.status === 'error') {
                form.reset();
            }

        } catch (err) {
            responseDiv.textContent = 'Unexpected error. Please try again.';
            responseDiv.style.color = 'red';
            responseDiv.style.display = 'block';
        }

        setTimeout(() => {
            responseDiv.style.display = 'none';
            responseDiv.textContent = '';
        }, 5000);
    });
}

document.addEventListener('DOMContentLoaded', function () {
    handleFormSubmission('login-form', 'response-message-login');
    handleFormSubmission('create-form', 'response-message-create');
});

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('forgot-password-form');
    const responseDiv = document.getElementById('response-message');

    form.addEventListener('submit', async function (e) {
        e.preventDefault();

        const formData = new FormData(form);

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            responseDiv.textContent = data.message;
            responseDiv.style.color = data.status === 'success' ? 'green' : 'red';
            responseDiv.style.display = 'block';

            if (data.status === 'success','error') {
                form.reset();
            }

            setTimeout(() => {
                responseDiv.style.display = 'none';
                responseDiv.textContent = '';
            }, 5000);
        } catch (err) {
            responseDiv.textContent = 'Unexpected error. Please try again.';
            responseDiv.style.color = 'red';
            responseDiv.style.display = 'block';

            setTimeout(() => {
                responseDiv.style.display = 'none';
                responseDiv.textContent = '';
            }, 5000);
        }
    });
});

window.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const modalMap = {
        'signup': 'create',            // signup form modal
        'login': 'login',              // login modal
        'forgot': 'forgot'    // forgot password modal
    };

    const modalId = modalMap[params.get('show')];
    if (modalId) {
        const modalElement = document.getElementById(modalId);
        if (modalElement) {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();

            history.replaceState(null, '', window.location.pathname);
        }
    }
});
(function() {
    let currentPage = 1;
    const totalPages = 3;
    const formData = {};

    const PASSWORD_POLICY = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z0-9]).{12,}$/;

    // ---- Stage routing (landing -> apply -> login/signup -> [verify-email] ->
    // profile-setup -> resume-upload -> resume-parsing -> application) ----

    function currentStage() {
        const hash = (window.location.hash || '#/').replace(/^#\/?/, '');
        return hash === '' ? 'landing' : hash;
    }

    function showStage(stage) {
        document.querySelectorAll('.stage').forEach(el => {
            el.style.display = el.dataset.stage === stage ? 'block' : 'none';
        });
        hideError();
        window.scrollTo(0, 0);
    }

    function route() {
        const stage = currentStage();
        showStage(stage);
        if (stage === 'resume-parsing') {
            // Auto-advance after a simulated parse delay - no user action here,
            // this stage exists specifically to exercise RESUME_PARSE_WAIT.
            setTimeout(() => { window.location.hash = '#/application'; }, 1500);
        }
        if (stage === 'application') {
            updateProgress();
        }
    }

    // ---- Pre-application flow ----

    function setupPreApplicationListeners() {
        const applyBtn = document.getElementById('apply-btn');
        if (applyBtn) applyBtn.addEventListener('click', () => { window.location.hash = '#/apply'; });

        const showLoginBtn = document.getElementById('show-login-btn');
        if (showLoginBtn) showLoginBtn.addEventListener('click', () => { window.location.hash = '#/login'; });

        const showSignupBtn = document.getElementById('show-signup-btn');
        if (showSignupBtn) showSignupBtn.addEventListener('click', () => { window.location.hash = '#/signup'; });

        const loginForm = document.getElementById('login-form');
        if (loginForm) loginForm.addEventListener('submit', handleLogin);

        const signupForm = document.getElementById('signup-form');
        if (signupForm) signupForm.addEventListener('submit', handleSignup);

        const profileSetupForm = document.getElementById('profile-setup-form');
        if (profileSetupForm) profileSetupForm.addEventListener('submit', handleProfileSetup);

        const resumeUploadForm = document.getElementById('resume-upload-form');
        if (resumeUploadForm) resumeUploadForm.addEventListener('submit', handleResumeUpload);
    }

    async function handleLogin(e) {
        e.preventDefault();
        const email = document.querySelector('[name="login_email"]').value;
        const password = document.querySelector('[name="login_password"]').value;

        // Real server-side account check (see server.py's _ACCOUNTS), not
        // localStorage - a fresh Playwright browser context has no access to
        // another context's localStorage, so client-side storage can't
        // simulate an account surviving across separate login attempts the
        // way a real ATS backend does.
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const result = await response.json();

        if (!result.success) {
            showError(result.error || 'Incorrect email or password');
            return;
        }

        hideError();
        window.location.hash = '#/profile-setup';
    }

    async function handleSignup(e) {
        e.preventDefault();
        const email = document.querySelector('[name="signup_email"]').value;
        const password = document.querySelector('[name="signup_password"]').value;
        const confirmPassword = document.querySelector('[name="signup_confirm_password"]').value;

        if (password !== confirmPassword) {
            showError('Passwords do not match');
            return;
        }
        if (!PASSWORD_POLICY.test(password)) {
            showError('Password must be at least 12 characters and include uppercase, lowercase, a digit, and a symbol');
            return;
        }

        // Deterministic test hook: any email containing "verify" triggers the
        // email-verification dead end, so MANUAL_INTERVENTION is reproducible
        // in CI without a real mailbox. Do not build inbox automation for this.
        if (email.toLowerCase().includes('verify')) {
            document.getElementById('verify-email-address').textContent = email;
            hideError();
            window.location.hash = '#/verify-email';
            return;
        }

        const response = await fetch('/api/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const result = await response.json();

        if (!result.success) {
            showError(result.error || 'Could not create account');
            return;
        }

        hideError();
        window.location.hash = '#/profile-setup';
    }

    function handleProfileSetup(e) {
        e.preventDefault();
        const referralSource = document.querySelector('[name="referral_source"]').value;
        if (!referralSource) {
            showError('Please tell us how you heard about us');
            return;
        }
        hideError();
        window.location.hash = '#/resume-upload';
    }

    function handleResumeUpload(e) {
        e.preventDefault();
        const fileInput = document.querySelector('#resume-upload-form [name="resume"]');
        if (!fileInput || fileInput.files.length === 0) {
            showError('Please choose a resume file');
            return;
        }
        hideError();
        window.location.hash = '#/resume-parsing';
    }

    // ---- Existing multi-page application form (stage: application) ----

    function setupApplicationListeners() {
        document.querySelectorAll('.next-btn').forEach(btn => {
            btn.addEventListener('click', handleNext);
        });

        document.querySelectorAll('.prev-btn').forEach(btn => {
            btn.addEventListener('click', handlePrevious);
        });

        const submitBtn = document.getElementById('submit-btn');
        if (submitBtn) {
            submitBtn.addEventListener('click', handleSubmit);
        }

        document.querySelectorAll('#application-form input, #application-form select, #application-form textarea').forEach(input => {
            input.addEventListener('change', saveFormData);
        });
    }

    function saveFormData() {
        const inputs = document.querySelectorAll('#application-form input, #application-form select, #application-form textarea');
        inputs.forEach(input => {
            if (input.name && input.type !== 'file') {
                if (input.type === 'checkbox') {
                    formData[input.name] = input.checked;
                } else {
                    formData[input.name] = input.value;
                }
            }
        });
    }

    function handleNext(e) {
        e.preventDefault();

        const currentPageEl = document.querySelector(`.form-page[data-page="${currentPage}"]`);
        const requiredFields = currentPageEl.querySelectorAll('[required]');

        let valid = true;
        requiredFields.forEach(field => {
            if (!field.value) {
                valid = false;
                field.style.borderColor = '#dc3545';
                setTimeout(() => {
                    field.style.borderColor = '';
                }, 2000);
            }
        });

        if (!valid) {
            showError('Please fill in all required fields');
            return;
        }

        hideError();
        saveFormData();

        currentPageEl.style.display = 'none';

        currentPage++;
        const nextPageEl = document.querySelector(`.form-page[data-page="${currentPage}"]`);
        nextPageEl.style.display = 'block';

        if (currentPage === 3) {
            populateReview();
        }

        updateProgress();
        window.scrollTo(0, 0);
    }

    function handlePrevious(e) {
        e.preventDefault();

        saveFormData();
        hideError();

        const currentPageEl = document.querySelector(`.form-page[data-page="${currentPage}"]`);
        currentPageEl.style.display = 'none';

        currentPage--;
        const prevPageEl = document.querySelector(`.form-page[data-page="${currentPage}"]`);
        prevPageEl.style.display = 'block';

        updateProgress();
        window.scrollTo(0, 0);
    }

    function populateReview() {
        const reviewContent = document.getElementById('review-content');

        const fields = [
            { label: 'First Name', name: 'first_name' },
            { label: 'Last Name', name: 'last_name' },
            { label: 'Email', name: 'email' },
            { label: 'Phone', name: 'phone' },
            { label: 'LinkedIn', name: 'linkedin' },
            { label: 'Work Authorization', name: 'work_authorization' },
            { label: 'Interest', name: 'interest' },
            { label: 'Willing to Relocate', name: 'willing_to_relocate' },
        ];

        let html = '';
        fields.forEach(field => {
            const value = formData[field.name] || '-';
            html += `
                <div class="review-item">
                    <div class="review-label">${field.label}</div>
                    <div class="review-value">${value}</div>
                </div>
            `;
        });

        reviewContent.innerHTML = html;
    }

    function handleSubmit(e) {
        e.preventDefault();

        const termsCheckbox = document.querySelector('[name="terms"]');
        if (!termsCheckbox || !termsCheckbox.checked) {
            showError('Please confirm that all information is accurate');
            return;
        }

        hideError();
        saveFormData();

        const appId = 'MOCK-' + Math.floor(Math.random() * 100000);

        localStorage.setItem('last_application_id', appId);
        localStorage.setItem('application_data', JSON.stringify(formData));

        window.location.href = `confirmation.html?id=${appId}`;
    }

    function updateProgress() {
        const indicator = document.getElementById('page-indicator');
        indicator.textContent = `Page ${currentPage} of ${totalPages}`;

        const progressFill = document.getElementById('progress-fill');
        const progressPercent = (currentPage / totalPages) * 100;
        progressFill.style.width = progressPercent + '%';
    }

    function showError(message) {
        const errorEl = document.getElementById('error-message');
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }

    function hideError() {
        const errorEl = document.getElementById('error-message');
        errorEl.style.display = 'none';
    }

    document.addEventListener('DOMContentLoaded', function() {
        setupPreApplicationListeners();
        setupApplicationListeners();
        window.addEventListener('hashchange', route);
        route();
    });
})();

(function() {
    let currentPage = 1;
    const totalPages = 3;
    const formData = {};

    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        setupEventListeners();
        updateProgress();
    });

    function setupEventListeners() {
        // Next buttons
        document.querySelectorAll('.next-btn').forEach(btn => {
            btn.addEventListener('click', handleNext);
        });

        // Previous buttons
        document.querySelectorAll('.prev-btn').forEach(btn => {
            btn.addEventListener('click', handlePrevious);
        });

        // Submit button
        const submitBtn = document.getElementById('submit-btn');
        if (submitBtn) {
            submitBtn.addEventListener('click', handleSubmit);
        }

        // Track form changes
        document.querySelectorAll('input, select, textarea').forEach(input => {
            input.addEventListener('change', saveFormData);
        });
    }

    function saveFormData() {
        const inputs = document.querySelectorAll('input, select, textarea');
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
        
        // Validate current page
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

        // Hide current page
        currentPageEl.style.display = 'none';
        
        // Show next page
        currentPage++;
        const nextPageEl = document.querySelector(`.form-page[data-page="${currentPage}"]`);
        nextPageEl.style.display = 'block';

        // If on review page, populate review
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

        // Hide current page
        const currentPageEl = document.querySelector(`.form-page[data-page="${currentPage}"]`);
        currentPageEl.style.display = 'none';
        
        // Show previous page
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
            { label: 'Resume', name: 'resume' },
            { label: 'Interest', name: 'interest' },
        ];

        let html = '';
        fields.forEach(field => {
            let value = formData[field.name] || '-';
            
            // Handle file input
            if (field.name === 'resume') {
                const fileInput = document.querySelector('[name="resume"]');
                if (fileInput && fileInput.files.length > 0) {
                    value = fileInput.files[0].name;
                } else {
                    value = '-';
                }
            }

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
        
        // Check terms checkbox
        const termsCheckbox = document.querySelector('[name="terms"]');
        if (!termsCheckbox || !termsCheckbox.checked) {
            showError('Please confirm that all information is accurate');
            return;
        }

        hideError();
        saveFormData();

        // Generate application ID
        const appId = 'MOCK-' + Math.floor(Math.random() * 100000);
        
        // Store in localStorage to detect duplicate
        localStorage.setItem('last_application_id', appId);
        localStorage.setItem('application_data', JSON.stringify(formData));

        // Redirect to confirmation
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
})();

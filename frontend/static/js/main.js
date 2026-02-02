// Global variables
let selectedFiles = [];
let selectedFolders = [];
let currentUser = null;
let userLimits = null;
let uploadMode = 'files'; // 'files' or 'folder'

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    checkAuthStatus();
    loadUserLimits();
});

// Initialize application
function initializeApp() {
    // Setup axios defaults
    axios.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

    // Use the global API_BASE_URL set by the server (includes APPLICATION_ROOT)
    // This allows the app to work both directly and behind reverse proxy
    if (window.API_BASE_URL) {
        axios.defaults.baseURL = window.API_BASE_URL;
    }

    // Get CSRF token if available
    const token = document.querySelector('meta[name="csrf-token"]');
    if (token) {
        axios.defaults.headers.common['X-CSRF-TOKEN'] = token.getAttribute('content');
    }
}

// Setup event listeners
function setupEventListeners() {
    const filesDropZone = document.getElementById('files-drop-zone');
    const folderDropZone = document.getElementById('folder-drop-zone');
    const fileInput = document.getElementById('file-input');
    const folderInput = document.getElementById('folder-input');
    const processBtn = document.getElementById('process-btn');
    const filesModeBtn = document.getElementById('files-mode-btn');
    const folderModeBtn = document.getElementById('folder-mode-btn');

    // Mode switching
    filesModeBtn.addEventListener('click', () => switchMode('files'));
    folderModeBtn.addEventListener('click', () => switchMode('folder'));

    // Click to upload
    filesDropZone.addEventListener('click', () => fileInput.click());
    folderDropZone.addEventListener('click', () => {
        // Only approved registered users can upload folders
        if (currentUser && currentUser.is_approved) {
            folderInput.click();
        } else {
            showFolderRestrictionModal();
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    // Folder input change
    folderInput.addEventListener('change', (e) => {
        handleFolder(e.target.files);
    });

    // Drag and drop events for files
    setupDragAndDrop(filesDropZone, handleFiles);

      // Drag and drop events for folders
    setupDragAndDrop(folderDropZone, handleFolder);

    // Process button
    processBtn.addEventListener('click', processFiles);
}

// Setup drag and drop for a zone
function setupDragAndDrop(zone, handler) {
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('drag-active');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('drag-active');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-active');
        handler(e.dataTransfer.files);
    });
}

// Switch between file and folder upload modes
function switchMode(mode) {
    uploadMode = mode;
    const filesModeBtn = document.getElementById('files-mode-btn');
    const folderModeBtn = document.getElementById('folder-mode-btn');
    const filesDropZone = document.getElementById('files-drop-zone');
    const folderDropZone = document.getElementById('folder-drop-zone');

    if (mode === 'files') {
        filesModeBtn.classList.add('bg-indigo-600', 'text-white');
        filesModeBtn.classList.remove('bg-gray-200', 'text-gray-700');
        folderModeBtn.classList.add('bg-gray-200', 'text-gray-700');
        folderModeBtn.classList.remove('bg-indigo-600', 'text-white');
        filesDropZone.classList.remove('hidden');
        folderDropZone.classList.add('hidden');
    } else {
        // Check if user is approved registered
        if (!currentUser || !currentUser.is_approved) {
            showFolderRestrictionModal();
            switchMode('files');
            return;
        }
        folderModeBtn.classList.add('bg-indigo-600', 'text-white');
        folderModeBtn.classList.remove('bg-gray-200', 'text-gray-700');
        filesModeBtn.classList.add('bg-gray-200', 'text-gray-700');
        filesModeBtn.classList.remove('bg-indigo-600', 'text-white');
        folderDropZone.classList.remove('hidden');
        filesDropZone.classList.add('hidden');
    }
}

// Handle folder upload
function handleFolder(files) {
    const filesArray = Array.from(files);
    const pdfFiles = filesArray.filter(file => file.type === 'application/pdf');

    if (pdfFiles.length === 0) {
        showToast('No PDF files found in the folder', 'error');
        return;
    }

    // Store with relative paths
    selectedFolders = pdfFiles.map(file => ({
        file: file,
        path: file.webkitRelativePath || file.name
    }));

    // Update UI
    displaySelectedFiles();
    updateProcessButton();
    showToast(`${pdfFiles.length} PDF files found in folder`, 'success');
}

// Handle selected files
function handleFiles(files) {
    const filesArray = Array.from(files);
    const pdfFiles = filesArray.filter(file => file.type === 'application/pdf');

    if (pdfFiles.length === 0) {
        showToast('Please select PDF files only', 'error');
        return;
    }

    // Check if adding these files would exceed the limit
    const currentFileCount = selectedFiles.length;
    const maxFiles = userLimits?.max_files_per_submission || 5;
    const newFileCount = currentFileCount + pdfFiles.length;

    if (newFileCount > maxFiles) {
        showToast(`Cannot add ${pdfFiles.length} files. Maximum ${maxFiles} files allowed per session. Currently have ${currentFileCount} files.`, 'error');
        return;
    }

    // Check for duplicate files
    const duplicateFiles = [];
    pdfFiles.forEach(newFile => {
        const isDuplicate = selectedFiles.some(existingFile =>
            existingFile.name === newFile.name &&
            existingFile.size === newFile.size
        );
        if (isDuplicate) {
            duplicateFiles.push(newFile.name);
        }
    });

    if (duplicateFiles.length > 0) {
        showToast(`${duplicateFiles.length} duplicate file(s) skipped: ${duplicateFiles.slice(0, 3).join(', ')}${duplicateFiles.length > 3 ? '...' : ''}`, 'warning');
    }

    // Add only non-duplicate files
    const uniqueNewFiles = pdfFiles.filter(newFile => {
        return !selectedFiles.some(existingFile =>
            existingFile.name === newFile.name &&
            existingFile.size === newFile.size
        );
    });

    selectedFiles.push(...uniqueNewFiles);
    displaySelectedFiles();
    updateProcessButton();
}

// Display selected files
function displaySelectedFiles() {
    const filesList = document.getElementById('files-list');
    const filesContainer = document.getElementById('files-container');
    const filesToDisplay = uploadMode === 'folder' ? selectedFolders : selectedFiles;

    if (filesToDisplay.length === 0) {
        filesList.classList.add('hidden');
        return;
    }

    filesList.classList.remove('hidden');
    filesContainer.innerHTML = '';

    filesToDisplay.forEach((item, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'flex items-center justify-between p-3 bg-gray-50 rounded-lg';

        const fileName = uploadMode === 'folder' ? item.path : item.name;
        const fileSize = uploadMode === 'folder' ? item.file.size : item.size;
        const icon = uploadMode === 'folder' ? 'fa-folder-open text-yellow-600' : 'fa-file-pdf text-red-600';

        fileItem.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${icon} mr-3"></i>
                <div>
                    <p class="font-medium text-gray-900">${fileName}</p>
                    <p class="text-sm text-gray-500">${formatFileSize(fileSize)}</p>
                </div>
            </div>
            <button onclick="removeFile(${index})" class="text-red-600 hover:text-red-800">
                <i class="fas fa-times"></i>
            </button>
        `;
        filesContainer.appendChild(fileItem);
    });
}

// Remove file from selection
function removeFile(index) {
    if (uploadMode === 'folder') {
        selectedFolders.splice(index, 1);
    } else {
        selectedFiles.splice(index, 1);
    }
    displaySelectedFiles();
    updateProcessButton();
}

// Update process button state
function updateProcessButton() {
    const processBtn = document.getElementById('process-btn');
    const hasFiles = uploadMode === 'folder' ? selectedFolders.length > 0 : selectedFiles.length > 0;
    processBtn.disabled = !hasFiles;
}

// Process files
async function processFiles() {
    // Check files or folders
    const filesToProcess = uploadMode === 'folder' ? selectedFolders : selectedFiles;
    if (filesToProcess.length === 0) {
        showToast('Please select files or a folder to process', 'error');
        return;
    }

    const processBtn = document.getElementById('process-btn');
    const totalFiles = filesToProcess.length;

    // Show processing modal
    showProcessingModal(filesToProcess);
    processBtn.disabled = true;
    processBtn.innerHTML = '<i class="fas fa-spinner animate-spin mr-2"></i>Processing...';

    // Prepare form data
    const formData = new FormData();
    if (uploadMode === 'folder') {
        selectedFolders.forEach(item => {
            formData.append('files', item.file);
            formData.append('paths', item.path);
        });
        formData.append('preserve_structure', 'true');
    } else {
        selectedFiles.forEach(file => {
            formData.append('files', file);
        });
    }

    try {
        // Update individual file progress
        filesToProcess.forEach((item, index) => {
            const name = uploadMode === 'folder' ? item.path : item.name;
            updateFileProgress(name, 'Processing...', 50);
        });

        // Send request
        const response = await axios.post('/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            },
            onUploadProgress: (progressEvent) => {
                const percentCompleted = Math.round(
                    (progressEvent.loaded * 100) / progressEvent.total
                );
                updateModalProgress(percentCompleted, 'Uploading files...');
            }
        });

        // Update progress to show processing complete
        updateModalProgress(100, 'Processing complete!');
        filesToProcess.forEach(item => {
            const name = uploadMode === 'folder' ? item.path : item.name;
            updateFileProgress(name, 'Complete', 100);
        });

        // Handle response - transition modal to complete state
        if (response.data.download_url) {
            // Short delay then show results
            setTimeout(() => {
                showResultsInModal(response.data, totalFiles);

                // Start download
                setTimeout(() => {
                    window.location.href = response.data.download_url;
                }, 500);
            }, 800);
        }

    } catch (error) {
        console.error('Processing error:', error);
        const errorMsg = error.response?.data?.error || 'Processing failed';

        // Update failed files in modal
        if (error.response?.data?.details) {
            error.response.data.details.forEach(detail => {
                const fileName = detail.split(':')[0];
                updateFileProgress(fileName, 'Failed', 0, 'error');
            });
        }

        // Show error in modal
        showErrorInModal(errorMsg, error.response?.data?.details);
    } finally {
        // Reset button
        processBtn.disabled = false;
        processBtn.innerHTML = '<i class="fas fa-magic mr-2"></i>Process Files';
        selectedFiles = [];
        selectedFolders = [];
        displaySelectedFiles();
        document.getElementById('file-input').value = '';
        document.getElementById('folder-input').value = '';
    }
}

// Show processing modal
function showProcessingModal(files) {
    const modal = document.getElementById('processing-modal');
    const progressList = document.getElementById('modal-progress-list');
    const processingState = document.getElementById('processing-state');
    const completeState = document.getElementById('complete-state');
    const closeBtn = document.getElementById('processing-modal-close');
    const modalIcon = document.getElementById('processing-modal-icon');
    const modalText = document.getElementById('processing-modal-text');

    // Reset to processing state
    processingState.classList.remove('hidden');
    completeState.classList.add('hidden');
    closeBtn.classList.add('hidden');
    modalIcon.className = 'fas fa-spinner fa-spin mr-2 text-indigo-600';
    modalText.textContent = 'Processing Files...';

    // Reset progress
    document.getElementById('modal-overall-progress').style.width = '0%';
    document.getElementById('modal-progress-text').textContent = 'Uploading files...';

    // Create progress items
    progressList.innerHTML = '';
    files.forEach(item => {
        const name = uploadMode === 'folder' ? item.path : item.name;
        const progressItem = createProgressItem(name);
        progressList.appendChild(progressItem);
    });

    // Show modal
    modal.classList.remove('hidden');
}

// Update modal progress bar
function updateModalProgress(percent, text) {
    const progressBar = document.getElementById('modal-overall-progress');
    const progressText = document.getElementById('modal-progress-text');

    progressBar.style.width = `${percent}%`;
    if (text) {
        progressText.textContent = text;
    }
}

// Show results in the same modal (transition to complete state)
function showResultsInModal(data, totalSubmitted = 1) {
    const processingState = document.getElementById('processing-state');
    const completeState = document.getElementById('complete-state');
    const closeBtn = document.getElementById('processing-modal-close');
    const modalIcon = document.getElementById('processing-modal-icon');
    const modalText = document.getElementById('processing-modal-text');
    const content = document.getElementById('results-content');

    // Update header to show completion
    modalIcon.className = 'fas fa-check-circle mr-2 text-green-600';
    modalText.textContent = 'Processing Complete!';
    closeBtn.classList.remove('hidden');

    // Calculate statistics
    const successCount = data.files ? data.files.length : (data.file ? 1 : 0);
    const errorCount = data.errors ? data.errors.length : 0;
    const successRate = Math.round((successCount / totalSubmitted) * 100);

    // Update summary statistics
    document.getElementById('stat-total').textContent = totalSubmitted;
    document.getElementById('stat-success').textContent = successCount;
    document.getElementById('stat-failed').textContent = errorCount;
    document.getElementById('stat-success-rate').textContent = `${successRate}%`;

    // Build results content
    let html = '<div class="space-y-4">';

    if (data.file) {
        // Single file
        html += `
            <div class="bg-green-50 p-4 rounded-lg">
                <h3 class="font-semibold text-green-800 mb-2">File Renamed Successfully</h3>
                <p class="text-sm text-gray-700">
                    <strong>Original:</strong> ${data.file.original_name}<br>
                    <strong>New Name:</strong> ${data.file.new_name}
                </p>
            </div>
        `;
    } else if (data.files && data.files.length > 0) {
        // Multiple files
        html += '<h3 class="font-semibold text-gray-900 mb-2">Successfully Renamed Files:</h3>';
        html += '<div class="max-h-40 overflow-y-auto space-y-2">';
        data.files.forEach(file => {
            html += `
                <div class="bg-gray-50 p-3 rounded">
                    <p class="text-sm"><strong>${file.original_name}</strong> &rarr; ${file.new_name}</p>
                </div>
            `;
        });
        html += '</div>';
    }

    if (data.errors && data.errors.length > 0) {
        html += `
            <div class="bg-yellow-50 p-4 rounded-lg">
                <h3 class="font-semibold text-yellow-800 mb-2">Errors:</h3>
                <ul class="text-sm text-yellow-700 space-y-1">
                    ${data.errors.map(error => `<li>&bull; ${error}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    html += `
        <div class="bg-blue-50 p-4 rounded-lg">
            <p class="text-sm text-blue-800">
                <i class="fas fa-download mr-1"></i>
                Your download should start automatically. If not,
                <a href="${data.download_url}" class="underline font-semibold">click here</a>.
            </p>
        </div>
    </div>`;

    content.innerHTML = html;

    // Transition to complete state
    processingState.classList.add('hidden');
    completeState.classList.remove('hidden');
}

// Show error in modal
function showErrorInModal(errorMsg, details) {
    const processingState = document.getElementById('processing-state');
    const completeState = document.getElementById('complete-state');
    const closeBtn = document.getElementById('processing-modal-close');
    const modalIcon = document.getElementById('processing-modal-icon');
    const modalText = document.getElementById('processing-modal-text');
    const content = document.getElementById('results-content');

    // Update header to show error
    modalIcon.className = 'fas fa-exclamation-circle mr-2 text-red-600';
    modalText.textContent = 'Processing Failed';
    closeBtn.classList.remove('hidden');

    // Hide summary stats for errors
    document.getElementById('summary-stats').classList.add('hidden');

    // Build error content
    let html = `
        <div class="bg-red-50 p-4 rounded-lg">
            <h3 class="font-semibold text-red-800 mb-2">Error</h3>
            <p class="text-sm text-red-700">${errorMsg}</p>
        </div>
    `;

    if (details && details.length > 0) {
        html += `
            <div class="bg-yellow-50 p-4 rounded-lg mt-4">
                <h3 class="font-semibold text-yellow-800 mb-2">Details:</h3>
                <ul class="text-sm text-yellow-700 space-y-1">
                    ${details.map(d => `<li>&bull; ${d}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    content.innerHTML = html;

    // Transition to complete state (showing error)
    processingState.classList.add('hidden');
    completeState.classList.remove('hidden');
}

// Close processing modal
function closeProcessingModal() {
    document.getElementById('processing-modal').classList.add('hidden');
    // Show summary stats again for next time
    document.getElementById('summary-stats').classList.remove('hidden');
}

// Create progress item for file
function createProgressItem(fileName) {
    const div = document.createElement('div');
    div.className = 'flex items-center justify-between p-3 bg-gray-50 rounded-lg';
    div.id = `progress-${fileName.replace(/[^a-zA-Z0-9]/g, '-')}`;
    div.innerHTML = `
        <div class="flex items-center flex-1">
            <i class="fas fa-file-pdf text-red-600 mr-3"></i>
            <div class="flex-1">
                <p class="font-medium text-gray-900 text-sm">${fileName}</p>
                <p class="text-xs text-gray-500 status-text">Waiting...</p>
            </div>
        </div>
        <div class="ml-4">
            <div class="w-24 bg-gray-200 rounded-full h-2">
                <div class="progress-fill bg-indigo-600 h-2 rounded-full" style="width: 0%"></div>
            </div>
        </div>
    `;
    return div;
}

// Update file progress
function updateFileProgress(fileName, status, percent, type = 'success') {
    const elementId = `progress-${fileName.replace(/[^a-zA-Z0-9]/g, '-')}`;
    const element = document.getElementById(elementId);

    if (!element) return;

    const statusText = element.querySelector('.status-text');
    const progressFill = element.querySelector('.progress-fill');

    statusText.textContent = status;
    progressFill.style.width = `${percent}%`;

    if (type === 'error') {
        progressFill.className = 'progress-fill bg-red-600 h-2 rounded-full';
        statusText.className = 'text-xs text-red-600 status-text';
    } else if (percent === 100) {
        progressFill.className = 'progress-fill bg-green-600 h-2 rounded-full';
        statusText.className = 'text-xs text-green-600 status-text';
    }
}


// Load user limits
async function loadUserLimits() {
    try {
        const response = await axios.get('/limits');
        userLimits = response.data;
        updateLimitsDisplay();
    } catch (error) {
        console.error('Error loading limits:', error);
    }
}

// Update limits display
function updateLimitsDisplay() {
    const limitsText = document.getElementById('limits-text');
    const registerCTA = document.getElementById('register-cta');

    if (!userLimits) return;
    if (!limitsText) return;

    // Display only file count limit - no submission time limits
    const maxFiles = userLimits.max_files_per_submission;
    limitsText.textContent = `You can upload up to ${maxFiles} files per submission.`;

    // Only manipulate registerCTA if it exists
    if (registerCTA) {
        if (userLimits.is_registered && userLimits.is_approved) {
            registerCTA.classList.add('hidden');
        } else if (userLimits.is_registered && !userLimits.is_approved) {
            limitsText.textContent += ` Account pending approval.`;
            registerCTA.classList.add('hidden');
        } else {
            registerCTA.classList.remove('hidden');
        }
    }
}

// Check authentication status
async function checkAuthStatus() {
    // JWT is now stored in HttpOnly cookie, sent automatically with requests
    try {
        const response = await axios.get('/auth/me');
        currentUser = response.data.user;
        updateAuthUI(currentUser);
    } catch (error) {
        // Not authenticated or session expired
        currentUser = null;
        updateAuthUI(null);
    }
}

// Update authentication UI
function updateAuthUI(user) {
    const authSection = document.getElementById('auth-section');
    const userMenu = document.getElementById('user-menu');
    const userNameEl = document.getElementById('user-name');
    const userEmailEl = document.getElementById('user-email');
    const userInitialsEl = document.getElementById('user-initials');

    // Update user data in menu
    if (user && userNameEl) {
        userNameEl.textContent = user.name;
        userEmailEl.textContent = user.email;
        userInitialsEl.textContent = user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

        // Show/hide admin panel link
        const adminLink = document.getElementById('admin-panel-link');
        if (adminLink) {
            if (user.is_admin) {
                adminLink.classList.remove('hidden');
            } else {
                adminLink.classList.add('hidden');
            }
        }
    }

    if (user) {
        // Show user profile dropdown
        currentUser = user;
        currentUser.is_registered = true;

        authSection.innerHTML = `
            <div class="flex items-center space-x-3">
                <span class="text-sm text-gray-700">Welcome, <span class="font-semibold">${user.name}</span></span>
                ${!user.is_approved ? '<span class="px-2 py-1 text-xs bg-yellow-100 text-yellow-800 rounded-full">Pending Approval</span>' : ''}
                <div class="relative">
                    <button onclick="toggleUserMenu(event)" class="text-gray-700 hover:text-indigo-600">
                        <i class="fas fa-user-circle text-xl"></i>
                    </button>
                </div>
            </div>
        `;
    } else {
        currentUser = null;
        userMenu.classList.add('hidden');

        authSection.innerHTML = `
            <button onclick="showLoginModal()" class="text-gray-700 hover:text-indigo-600 px-3 py-2 rounded-md text-sm font-medium">
                Login
            </button>
            <button onclick="showRegisterModal()" class="bg-indigo-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-indigo-700">
                Register
            </button>
        `;
    }
}

// Toggle user menu
function toggleUserMenu(event) {
    const userMenu = document.getElementById('user-menu');

    // Toggle visibility
    const isHidden = userMenu.classList.toggle('hidden');

    // If showing the menu, position it below the button
    if (!isHidden) {
        // Get the button element (either from event or by finding the user icon button)
        const button = event?.target?.closest('button') ||
                       document.querySelector('button[onclick^="toggleUserMenu"]') ||
                       document.querySelector('.fa-user-circle')?.closest('button');

        if (button) {
            const buttonRect = button.getBoundingClientRect();
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

            // Position menu below the button, aligned to the right
            userMenu.style.position = 'absolute';
            userMenu.style.top = (buttonRect.bottom + scrollTop + 4) + 'px';
            userMenu.style.right = 'auto';
            userMenu.style.left = (buttonRect.left + scrollLeft) + 'px';
        }
    }
}

// Close user menu when clicking outside
document.addEventListener('click', function(event) {
    const userMenu = document.getElementById('user-menu');
    const userIcon = event.target.closest('button[onclick^="toggleUserMenu"]');

    if (!userIcon && !userMenu.contains(event.target)) {
        userMenu.classList.add('hidden');
    }
});

// Show login modal
function showLoginModal() {
    document.getElementById('login-modal').classList.remove('hidden');
}

// Show register modal
function showRegisterModal() {
    document.getElementById('register-modal').classList.remove('hidden');
}

// Close login modal
function closeLoginModal() {
    document.getElementById('login-modal').classList.add('hidden');
    document.getElementById('login-form').reset();
}

// Close register modal
function closeRegisterModal() {
    document.getElementById('register-modal').classList.add('hidden');
    document.getElementById('register-form').reset();
}

// Show folder restriction modal
function showFolderRestrictionModal() {
    document.getElementById('folder-restriction-modal').classList.remove('hidden');
}

// Close folder restriction modal
function closeFolderRestrictionModal() {
    document.getElementById('folder-restriction-modal').classList.add('hidden');
}

// Switch to register modal
function switchToRegister() {
    closeLoginModal();
    showRegisterModal();
}

// Switch to login modal
function switchToLogin() {
    closeRegisterModal();
    showLoginModal();
}

// Handle login
async function handleLogin(event) {
    event.preventDefault();

    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const remember = document.getElementById('login-remember').checked;
    const loginBtn = document.getElementById('login-btn');

    loginBtn.disabled = true;
    loginBtn.innerHTML = '<i class="fas fa-spinner animate-spin mr-2"></i>Logging in...';

    try {
        const response = await axios.post(`${window.API_BASE_URL}/auth/login`, {
            email: email,
            password: password,
            remember: remember
        });

        // JWT token is now stored in HttpOnly cookie (not localStorage) for XSS protection
        // Cookie is automatically sent with requests, no manual token handling needed

        // Update UI
        updateAuthUI(response.data.user);
        showToast('Login successful!', 'success');
        closeLoginModal();

        // Reload limits and auth status
        checkAuthStatus();
        loadUserLimits();

    } catch (error) {
        const errorMsg = error.response?.data?.error || 'Login failed';
        showToast(errorMsg, 'error');
    } finally {
        loginBtn.disabled = false;
        loginBtn.innerHTML = 'Login';
    }
}

// Handle register
async function handleRegister(event) {
    event.preventDefault();

    const name = document.getElementById('register-name').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const confirmPassword = document.getElementById('register-confirm-password').value;
    const terms = document.getElementById('register-terms').checked;
    const registerBtn = document.getElementById('register-btn');

    // Validate passwords match
    if (password !== confirmPassword) {
        showToast('Passwords do not match', 'error');
        return;
    }

    registerBtn.disabled = true;
    registerBtn.innerHTML = '<i class="fas fa-spinner animate-spin mr-2"></i>Registering...';

    try {
        const response = await axios.post('/auth/register', {
            name: name,
            email: email,
            password: password
        });

        // JWT token is now stored in HttpOnly cookie (not localStorage) for XSS protection
        // Cookie is automatically sent with requests, no manual token handling needed

        // Update UI
        updateAuthUI(response.data.user);
        showToast(response.data.message, 'success');
        closeRegisterModal();

        // Reload limits and auth status
        checkAuthStatus();
        loadUserLimits();

    } catch (error) {
        const errorMsg = error.response?.data?.error || 'Registration failed';
        showToast(errorMsg, 'error');
    } finally {
        registerBtn.disabled = false;
        registerBtn.innerHTML = 'Register';
    }
}

// Handle logout
async function logout() {
    try {
        // Logout clears the HttpOnly JWT cookie server-side
        await axios.post('/auth/logout');
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        // Clear local data (but not auth_token - that's now in HttpOnly cookie)
        currentUser = null;
        updateAuthUI(null);
        showToast('Logged out successfully', 'success');
        // Now load the anonymous user limits
        loadUserLimits();
    }
}

// Show change password modal
function showChangePasswordModal() {
    document.getElementById('change-password-modal').classList.remove('hidden');
    document.getElementById('user-menu').classList.add('hidden');
}

// Close change password modal
function closeChangePasswordModal() {
    document.getElementById('change-password-modal').classList.add('hidden');
    document.getElementById('change-password-form').reset();
}

// Handle change password
async function handleChangePassword(event) {
    event.preventDefault();

    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-new-password').value;
    const changeBtn = document.getElementById('change-password-btn');

    // Validate passwords match
    if (newPassword !== confirmPassword) {
        showToast('New passwords do not match', 'error');
        return;
    }

    changeBtn.disabled = true;
    changeBtn.innerHTML = '<i class="fas fa-spinner animate-spin mr-2"></i>Changing...';

    try {
        // JWT cookie is sent automatically
        const response = await axios.post('/auth/change-password', {
            current_password: currentPassword,
            new_password: newPassword
        });

        showToast(response.data.message, 'success');
        closeChangePasswordModal();

    } catch (error) {
        const errorMsg = error.response?.data?.error || 'Password change failed';
        showToast(errorMsg, 'error');
    } finally {
        changeBtn.disabled = false;
        changeBtn.innerHTML = 'Change Password';
    }
}

// Show usage stats
async function showUsageStats() {
    try {
        // JWT cookie is sent automatically
        const response = await axios.get('/usage-stats');

        const stats = response.data;

        // Create and show usage stats modal
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
                <div class="flex justify-between items-center mb-6">
                    <h3 class="text-2xl font-bold text-gray-900">Your Usage Statistics</h3>
                    <button onclick="closeModal(this)" class="text-gray-400 hover:text-gray-600">
                        <i class="fas fa-times text-xl"></i>
                    </button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                    <div class="text-center p-4 bg-blue-50 rounded-lg">
                        <div class="text-3xl font-bold text-blue-600">${stats.total_submissions}</div>
                        <div class="text-sm text-gray-600 mt-1">Total Submissions</div>
                    </div>
                    <div class="text-center p-4 bg-green-50 rounded-lg">
                        <div class="text-3xl font-bold text-green-600">${stats.total_files_processed}</div>
                        <div class="text-sm text-gray-600 mt-1">Files Processed</div>
                    </div>
                    <div class="text-center p-4 bg-purple-50 rounded-lg">
                        <div class="text-3xl font-bold text-purple-600">${stats.max_files_per_submission}</div>
                        <div class="text-sm text-gray-600 mt-1">Max Files per Upload</div>
                    </div>
                </div>

                ${stats.recent_submissions.length > 0 ? `
                    <div>
                        <h4 class="text-lg font-semibold text-gray-900 mb-3">Recent Activity</h4>
                        <div class="space-y-2 max-h-60 overflow-y-auto">
                            ${stats.recent_submissions.map(sub => `
                                <div class="flex justify-between items-center p-3 bg-gray-50 rounded">
                                    <div>
                                        <p class="text-sm font-medium">${sub.files_processed} files processed</p>
                                        <p class="text-xs text-gray-500">${new Date(sub.timestamp).toLocaleString()}</p>
                                    </div>
                                    <span class="text-xs text-gray-500">IP: ${sub.ip_address}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : '<p class="text-center text-gray-500">No recent activity</p>'}

                <div class="mt-6 pt-4 border-t">
                    <div class="flex items-center justify-between">
                        <span class="text-sm text-gray-600">Account Status:</span>
                        <span class="px-3 py-1 rounded-full text-xs font-medium ${
                            stats.is_approved ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                        }">
                            ${stats.is_approved ? 'Approved Account' : 'Pending Approval'}
                        </span>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });

    } catch (error) {
        console.error('Error loading usage stats:', error);
        showToast('Error loading usage stats', 'error');
    }
}

// Close modal
function closeModal(element) {
    element.closest('.fixed').remove();
}

// Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');

    const bgColor = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        warning: 'bg-yellow-500',
        info: 'bg-blue-500'
    }[type];

    toast.className = `${bgColor} text-white px-6 py-3 rounded-lg shadow-lg transform transition-all duration-300 translate-y-full opacity-0`;
    toast.innerHTML = `
        <div class="flex items-center">
            <i class="fas fa-${type === 'error' ? 'exclamation-circle' : 'info-circle'} mr-2"></i>
            <span>${message}</span>
        </div>
    `;

    container.appendChild(toast);

    // Animate in
    setTimeout(() => {
        toast.classList.remove('translate-y-full', 'opacity-0');
    }, 100);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.add('translate-y-full', 'opacity-0');
        setTimeout(() => {
            container.removeChild(toast);
        }, 300);
    }, 3000);
}

// ==================== INACTIVITY TIMEOUT SYSTEM ====================

// Configuration
const INACTIVITY_TIMEOUT = 30 * 60 * 1000; // 30 minutes in milliseconds
const WARNING_TIMEOUT = 2 * 60 * 1000; // 2 minutes warning before sign-out
const WARNING_MESSAGE_ID = 'inactivity-warning';

// Inactivity tracking variables
let inactivityTimer;
let warningTimer;
let lastActivityTime;
let isWarningShown = false;

// Initialize inactivity tracking
function initializeInactivityTracking() {
    // Don't track inactivity for unauthenticated users
    // Check if user is authenticated via the currentUser variable (set by checkAuthStatus)
    if (!currentUser) {
        return;
    }

    lastActivityTime = Date.now();
    resetInactivityTimer();
    setupActivityListeners();
    console.log('Inactivity tracking initialized with 30-minute timeout');
}

// Reset the inactivity timer
function resetInactivityTimer() {
    // Clear existing timers
    clearTimeout(inactivityTimer);
    clearTimeout(warningTimer);

    // Hide warning if it's shown
    hideInactivityWarning();

    // Set new warning timer (30 - 2 = 28 minutes)
    warningTimer = setTimeout(() => {
        showInactivityWarning();
    }, INACTIVITY_TIMEOUT - WARNING_TIMEOUT);

    // Set new inactivity timer (30 minutes)
    inactivityTimer = setTimeout(() => {
        handleInactivityTimeout();
    }, INACTIVITY_TIMEOUT);

    lastActivityTime = Date.now();
}

// Setup activity event listeners
function setupActivityListeners() {
    const activityEvents = [
        'mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart',
        'click', 'keydown', 'keyup', 'focus', 'blur'
    ];

    activityEvents.forEach(eventType => {
        document.addEventListener(eventType, handleUserActivity, true);
    });

    // Also track page visibility changes
    document.addEventListener('visibilitychange', handleVisibilityChange);
}

// Handle user activity
function handleUserActivity(event) {
    // Don't track activity if user is not authenticated
    // Check if user is authenticated via the currentUser variable (set by checkAuthStatus)
    if (!currentUser) {
        return;
    }

    // Reset timer on any user interaction
    resetInactivityTimer();

    // ============================================================
    // DISABLED: Token Refresh Auto-Renewal (2024-01-15)
    // Reason: Causing API spam and authentication issues
    // Status: Intentionally disabled - not a bug
    // TODO: Re-evaluate if rate limiting is implemented
    // ============================================================
    // checkTokenRenewal();
}

// Handle page visibility change
function handleVisibilityChange() {
    if (!document.hidden && currentUser) {
        // Page became visible, check if we should show warning
        const timeSinceLastActivity = Date.now() - lastActivityTime;
        const timeUntilWarning = INACTIVITY_TIMEOUT - WARNING_TIMEOUT - timeSinceLastActivity;

        if (timeUntilWarning <= 0 && timeUntilWarning > -WARNING_TIMEOUT) {
            showInactivityWarning();
        }
    }
}

// Show inactivity warning
function showInactivityWarning() {
    if (isWarningShown) return;

    isWarningShown = true;

    const warningHtml = `
        <div id="${WARNING_MESSAGE_ID}" class="fixed top-0 left-0 w-full h-full bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6 border-4 border-yellow-400">
                <div class="text-center">
                    <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-yellow-100 mb-4">
                        <i class="fas fa-clock text-yellow-600 text-xl"></i>
                    </div>
                    <h3 class="text-lg font-bold text-gray-900 mb-2">Session Timeout Warning</h3>
                    <p class="text-gray-600 mb-6">
                        You will be automatically signed out due to inactivity in <strong>2 minutes</strong>.<br>
                        Click "Stay Active" to continue your session.
                    </p>
                    <div class="flex justify-center space-x-3">
                        <button onclick="hideInactivityWarning(); resetInactivityTimer();"
                                class="bg-indigo-600 text-white py-2 px-6 rounded-lg hover:bg-indigo-700 transition font-semibold">
                            <i class="fas fa-user-check mr-2"></i>Stay Active
                        </button>
                        <button onclick="handleInactivityTimeout();"
                                class="bg-gray-300 text-gray-700 py-2 px-6 rounded-lg hover:bg-gray-400 transition font-semibold">
                            <i class="fas fa-sign-out-alt mr-2"></i>Sign Out
                        </button>
                    </div>
                    <div class="mt-4">
                        <div class="bg-gray-200 rounded-full h-2 overflow-hidden">
                            <div id="inactivity-progress-bar" class="bg-yellow-500 h-full transition-all duration-1000 linear"
                                 style="width: 100%"></div>
                        </div>
                        <p class="text-xs text-gray-500 mt-2">Time remaining: <span id="inactivity-countdown">2:00</span></p>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', warningHtml);

    // Start countdown timer
    let timeRemaining = WARNING_TIMEOUT / 1000;
    const countdownElement = document.getElementById('inactivity-countdown');
    const progressBar = document.getElementById('inactivity-progress-bar');

    const countdownInterval = setInterval(() => {
        timeRemaining--;
        const minutes = Math.floor(timeRemaining / 60);
        const seconds = timeRemaining % 60;
        countdownElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        progressBar.style.width = `${(timeRemaining / (WARNING_TIMEOUT / 1000)) * 100}%`;

        if (timeRemaining <= 0) {
            clearInterval(countdownInterval);
        }
    }, 1000);
}

// Hide inactivity warning
function hideInactivityWarning() {
    const warningElement = document.getElementById(WARNING_MESSAGE_ID);
    if (warningElement) {
        warningElement.remove();
    }
    isWarningShown = false;
}

// Handle inactivity timeout
async function handleInactivityTimeout() {
    hideInactivityWarning();

    showToast('You have been signed out due to inactivity', 'warning');

    try {
        // Clear authentication
        await logout();
    } catch (error) {
        // Force logout even if API call fails
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_settings');
        window.location.href = '/';
    }
}

// Auto-renewal for approaching token expiration
async function checkTokenRenewal() {
    const token = localStorage.getItem('auth_token');
    if (!token) return;

    try {
        // Refresh token if needed (server will check if within 30 minutes of expiration)
        const response = await axios.post('/auth/refresh-token', {}, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.data.token) {
            // Update stored token with refreshed one
            localStorage.setItem('auth_token', response.data.token);

            // Update axios default header
            axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.token}`;

            console.log('Token refreshed successfully');
        }
    } catch (error) {
        console.log('Token refresh failed or not needed:', error.response?.data?.error || error.message);

        // If refresh fails due to authentication error, user may need to log in again
        if (error.response?.status === 401) {
            console.log('Token refresh failed - authentication required');
            showToast('Your session has expired. Please log in again.', 'warning');
        }
    }
}

// Initialize inactivity tracking when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Wait a short delay to ensure auth status is loaded
    setTimeout(() => {
        initializeInactivityTracking();

        // ============================================================
        // DISABLED: Token Refresh Auto-Renewal (2024-01-15)
        // Reason: Causing API spam and authentication issues
        // Status: Intentionally disabled - not a bug
        // TODO: Re-evaluate if rate limiting is implemented
        // ============================================================
        // setInterval(checkTokenRenewal, 10 * 60 * 1000);
    }, 1000);
});

// Clean up inactivity tracking when user logs out
const originalLogout = logout;
logout = async function() {
    // Clear inactivity timers
    clearTimeout(inactivityTimer);
    clearTimeout(warningTimer);
    hideInactivityWarning();

    // Remove event listeners
    const activityEvents = [
        'mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart',
        'click', 'keydown', 'keyup', 'focus', 'blur'
    ];

    activityEvents.forEach(eventType => {
        document.removeEventListener(eventType, handleUserActivity, true);
    });

    document.removeEventListener('visibilitychange', handleVisibilityChange);

    // Call original logout function
    return originalLogout.apply(this, arguments);
};

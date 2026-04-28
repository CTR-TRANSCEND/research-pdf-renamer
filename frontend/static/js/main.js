// Global variables
let selectedFiles = [];
let selectedFolders = [];
let currentUser = null;
let userLimits = null;
let uploadMode = 'files'; // 'files' or 'folder'
let _pollingInterval = null; // For progress polling

// HTML escaping utility to prevent XSS
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Trigger a file download without navigating the page.
// Using `window.location.href = url` would navigate (clobbering modal state)
// if the response is not actually a download (e.g. server returns HTML/JSON
// error). A hidden <a download> click stays on the current page in modern
// browsers; if the server returns an error body, the browser silently does
// nothing instead of navigating away.
function triggerDownload(url) {
    if (!url) return;
    const a = document.createElement('a');
    a.href = url;
    a.download = '';  // Hint browser to download rather than navigate
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => a.remove(), 0);
}

// ---------------------------------------------------------------------------
// Modal accessibility helper: Escape-to-close + focus return + simple focus trap.
// Applied to any element with role="dialog". Activates when the dialog becomes
// visible (i.e. its `hidden` class is removed).
// ---------------------------------------------------------------------------
const _modalState = new WeakMap(); // modalEl -> { previousFocus, keyHandler }

function _focusableInside(el) {
    return Array.from(el.querySelectorAll(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )).filter(e => e.offsetParent !== null);
}

function _activateModal(modal) {
    if (_modalState.has(modal)) return; // already active
    const previousFocus = document.activeElement;
    const keyHandler = (e) => {
        if (e.key === 'Escape') {
            // Find a close button inside the modal and click it; fall back to hiding.
            const closeBtn = modal.querySelector('[data-modal-close], [aria-label="Close"]');
            if (closeBtn) {
                e.preventDefault();
                closeBtn.click();
            } else {
                e.preventDefault();
                modal.classList.add('hidden');
                _deactivateModal(modal);
            }
        } else if (e.key === 'Tab') {
            const focusable = _focusableInside(modal);
            if (focusable.length === 0) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }
    };
    modal.addEventListener('keydown', keyHandler);
    _modalState.set(modal, { previousFocus, keyHandler });
    // Move focus into the modal
    const focusable = _focusableInside(modal);
    if (focusable.length > 0) focusable[0].focus();
}

function _deactivateModal(modal) {
    const state = _modalState.get(modal);
    if (!state) return;
    modal.removeEventListener('keydown', state.keyHandler);
    _modalState.delete(modal);
    if (state.previousFocus && typeof state.previousFocus.focus === 'function') {
        state.previousFocus.focus();
    }
}

function setupModalAccessibility() {
    // Watch every dialog for visibility changes (the app toggles a "hidden" class)
    const dialogs = document.querySelectorAll('[role="dialog"]');
    dialogs.forEach(dialog => {
        const observer = new MutationObserver(() => {
            if (dialog.classList.contains('hidden')) {
                _deactivateModal(dialog);
            } else {
                _activateModal(dialog);
            }
        });
        observer.observe(dialog, { attributes: true, attributeFilter: ['class'] });
        // Initial state
        if (!dialog.classList.contains('hidden')) {
            _activateModal(dialog);
        }
    });
}

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    setupModalAccessibility();
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
        axios.defaults.headers.common['X-CSRFToken'] = token.getAttribute('content');
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

    // Mode switching (only if buttons exist)
    if (filesModeBtn) {
        filesModeBtn.addEventListener('click', () => switchMode('files'));
    }
    if (folderModeBtn) {
        folderModeBtn.addEventListener('click', () => switchMode('folder'));
    }

    // Click to upload
    if (filesDropZone) {
        filesDropZone.addEventListener('click', () => fileInput.click());
    }
    if (folderDropZone) {
        folderDropZone.addEventListener('click', () => {
            // Only approved registered users can upload folders
            if (currentUser && currentUser.is_approved) {
                folderInput.click();
            } else {
                showFolderRestrictionModal();
            }
        });
    }

    // File input change
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
        });
    }

    // Folder input change
    if (folderInput) {
        folderInput.addEventListener('change', (e) => {
            handleFolder(e.target.files);
        });
    }

    // Drag and drop events for files
    if (filesDropZone) {
        setupDragAndDrop(filesDropZone, handleFiles);
    }

      // Drag and drop events for folders
    if (folderDropZone) {
        setupDragAndDrop(folderDropZone, handleFolder);
    }

    // Process button
    if (processBtn) {
        processBtn.addEventListener('click', processFiles);
    }
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

// File size limits (must mirror server-side MAX_CONTENT_LENGTH).
// Per-file hard cap rejects upload; total size soft cap warns only.
const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024;       // 50 MB per file
const TOTAL_SIZE_WARN_BYTES = 100 * 1024 * 1024;    // 100 MB combined

// Validate a list of File objects against size limits.
// Returns true if upload may proceed, false if a hard limit was hit.
// Shows a toast for both the hard reject and the soft warning cases.
function validateFileSizes(files) {
    // Hard reject: any single file over per-file cap
    const oversized = files.filter(f => f.size > MAX_FILE_SIZE_BYTES);
    if (oversized.length > 0) {
        const names = oversized.slice(0, 3).map(f => `${f.name} (${formatFileSize(f.size)})`).join(', ');
        const more = oversized.length > 3 ? `, and ${oversized.length - 3} more` : '';
        showToast(
            `File too large (max ${formatFileSize(MAX_FILE_SIZE_BYTES)} per file): ${names}${more}`,
            'error'
        );
        return false;
    }

    // Soft warning: combined size over total cap
    const totalSize = files.reduce((sum, f) => sum + f.size, 0);
    if (totalSize > TOTAL_SIZE_WARN_BYTES) {
        showToast(
            `Large upload: ${formatFileSize(totalSize)} total. This may take longer to process.`,
            'warning'
        );
    }

    return true;
}

// Handle folder upload
function handleFolder(files) {
    const filesArray = Array.from(files);
    const pdfFiles = filesArray.filter(file => file.type === 'application/pdf');

    if (pdfFiles.length === 0) {
        showToast('No PDF files found in the folder', 'error');
        return;
    }

    // Enforce per-file size cap; warn on large total.
    if (!validateFileSizes(pdfFiles)) {
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

    // Enforce per-file size cap; warn on large combined total (existing + new).
    const combinedForSize = [...selectedFiles, ...pdfFiles];
    if (!validateFileSizes(combinedForSize)) {
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
        fileItem.className = 'flex items-center justify-between py-1.5 px-3 bg-gray-50 rounded';

        const fileName = uploadMode === 'folder' ? item.path : item.name;
        const fileSize = uploadMode === 'folder' ? item.file.size : item.size;
        const icon = uploadMode === 'folder' ? 'fa-folder-open text-yellow-600' : 'fa-file-pdf text-red-600';

        fileItem.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${icon} mr-3"></i>
                <div>
                    <p class="font-medium text-gray-900">${escapeHtml(fileName)}</p>
                    <p class="text-sm text-gray-500">${escapeHtml(formatFileSize(fileSize))}</p>
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

// Format elapsed time for display
function formatElapsedTime(seconds) {
    if (seconds < 60) {
        return `${seconds.toFixed(1)} seconds`;
    } else {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.round(seconds % 60);
        return `${minutes} minute${minutes > 1 ? 's' : ''} ${remainingSeconds} second${remainingSeconds !== 1 ? 's' : ''}`;
    }
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
            updateFileProgress(name, 'Waiting...', 0);
        });

        // Send request with upload progress tracking
        const response = await axios.post('upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            },
            timeout: 60000, // 1 minute timeout for upload only (processing is async now)
            onUploadProgress: (progressEvent) => {
                const percentCompleted = Math.round(
                    (progressEvent.loaded * 100) / progressEvent.total
                );
                updateModalProgress(percentCompleted, `Uploading files... ${percentCompleted}%`);
            }
        });

        // Upload returned job_id - start polling for progress
        const jobId = response.data.job_id;
        if (!jobId) {
            // Fallback: old-style synchronous response (shouldn't happen but be safe)
            handleSynchronousResponse(response.data, filesToProcess, totalFiles);
            return;
        }

        // Switch UI to processing state
        updateModalProgress(100, `Processing 0 of ${totalFiles} files with AI...`);
        filesToProcess.forEach(item => {
            const name = uploadMode === 'folder' ? item.path : item.name;
            updateFileProgress(name, 'Processing...', 25);
        });

        // Start polling
        startProgressPolling(jobId, filesToProcess, totalFiles);

    } catch (error) {
        console.error('Processing error:', error);
        let errorMsg = error.response?.data?.error || 'Processing failed';

        // Provide user-friendly messages for common HTTP errors
        if (error.response?.status === 413) {
            errorMsg = 'Upload too large. Please reduce the number of files or use smaller PDFs.';
        } else if (error.response?.status === 429) {
            errorMsg = 'Rate limit exceeded. Please wait a moment and try again.';
        } else if (error.response?.status === 504 || error.code === 'ECONNABORTED') {
            errorMsg = 'Request timed out. Try uploading fewer files at a time.';
        } else if (!error.response) {
            errorMsg = 'Network error. Please check your connection and try again.';
        }

        // Update failed files in modal
        if (error.response?.data?.details) {
            error.response.data.details.forEach(detail => {
                const fileName = detail.split(':')[0];
                updateFileProgress(fileName, 'Failed', 0, 'error');
            });
        }

        showErrorInModal(errorMsg, error.response?.data?.details);
        resetProcessButton();
    }
}

// Start polling for job progress
function startProgressPolling(jobId, filesToProcess, totalFiles) {
    // Clear any existing polling
    if (_pollingInterval) {
        clearInterval(_pollingInterval);
        _pollingInterval = null;
    }

    // Track failure / stuck state
    let consecutiveFailures = 0;
    const MAX_CONSECUTIVE_FAILURES = 6;  // ~30s of failed polls
    let lastCompletedCount = -1;
    let lastProgressTime = Date.now();
    const STUCK_TIMEOUT_MS = 5 * 60 * 1000;  // 5 minutes with no progress

    const stopPolling = (reason) => {
        if (_pollingInterval) {
            clearInterval(_pollingInterval);
            _pollingInterval = null;
        }
        showErrorInModal(reason, null);
        resetProcessButton();
    };

    _pollingInterval = setInterval(async () => {
        try {
            const response = await axios.get(`upload/progress/${jobId}`, { timeout: 10000 });
            consecutiveFailures = 0;
            const progress = response.data;

            // Stuck detection: if completed count hasn't moved in 5 minutes, assume backend died
            if (progress.completed !== lastCompletedCount) {
                lastCompletedCount = progress.completed;
                lastProgressTime = Date.now();
            } else if (progress.status === 'processing' && Date.now() - lastProgressTime > STUCK_TIMEOUT_MS) {
                stopPolling('Processing appears stuck (no progress for 5 minutes). The server may have crashed. Please try again.');
                return;
            }

            // Update overall progress
            const completedCount = progress.completed;
            const pct = totalFiles > 0 ? Math.round((completedCount / totalFiles) * 100) : 0;
            updateModalProgress(pct, `Processing ${completedCount} of ${totalFiles} files with AI...`);

            // Update individual file statuses
            if (progress.files) {
                progress.files.forEach(fileStatus => {
                    if (fileStatus.status === 'extracting') {
                        updateFileProgress(fileStatus.name, 'Extracting text...', 20);
                    } else if (fileStatus.status === 'analyzing') {
                        updateFileProgress(fileStatus.name, 'Analyzing with AI...', 50);
                    } else if (fileStatus.status === 'retrying') {
                        updateFileProgress(fileStatus.name, 'Retrying AI analysis...', 50);
                    } else if (fileStatus.status === 'renaming') {
                        updateFileProgress(fileStatus.name, 'Renaming...', 80);
                    } else if (fileStatus.status === 'complete') {
                        const displayText = fileStatus.new_name
                            ? `Done: ${fileStatus.new_name}`
                            : 'Complete';
                        updateFileProgress(fileStatus.name, displayText, 100, 'success');
                    } else if (fileStatus.status === 'error') {
                        const errText = fileStatus.error
                            ? fileStatus.error.split(':').slice(1).join(':').trim() || 'Failed'
                            : 'Failed';
                        updateFileProgress(fileStatus.name, errText, 100, 'error');
                    } else if (fileStatus.status === 'pending') {
                        updateFileProgress(fileStatus.name, 'Waiting...', 5);
                    }
                });
            }

            // Check if done
            if (progress.status === 'complete' || progress.status === 'error') {
                clearInterval(_pollingInterval);
                _pollingInterval = null;

                // Build a response-like data object for showResultsInModal
                const resultData = {
                    download_url: progress.download_url,
                    errors: progress.errors || [],
                    elapsed_seconds: progress.elapsed_seconds,
                };

                // Populate files from progress
                if (progress.processed_files && progress.processed_files.length > 0) {
                    if (progress.processed_files.length === 1) {
                        resultData.file = progress.processed_files[0];
                    } else {
                        resultData.files = progress.processed_files;
                    }
                    resultData.message = `Successfully processed ${progress.processed_files.length} files`;
                } else {
                    resultData.files = [];
                }

                // Store failed file objects for retry
                if (resultData.errors && resultData.errors.length > 0) {
                    const failedNames = resultData.errors.map(e => {
                        const colonIdx = e.indexOf(':');
                        return colonIdx > 0 ? e.substring(0, colonIdx).trim() : '';
                    });
                    window._lastFailedFileObjects = filesToProcess.filter(item => {
                        const name = uploadMode === 'folder' ? item.path : item.name;
                        return failedNames.some(fn => name === fn || name.includes(fn));
                    });
                } else {
                    window._lastFailedFileObjects = [];
                }

                // Show results
                updateModalProgress(100, 'Processing complete!');

                setTimeout(() => {
                    showResultsInModal(resultData, totalFiles);
                    if (resultData.download_url) {
                        setTimeout(() => {
                            triggerDownload(resultData.download_url);
                        }, 500);
                    }
                }, 500);

                resetProcessButton();
            }

        } catch (pollError) {
            console.error('Polling error:', pollError);
            consecutiveFailures++;
            // If the job ID is gone (404), the backend forgot it — give up
            if (pollError.response?.status === 404) {
                stopPolling('Job expired or not found. The processing job is no longer available. Please try again.');
                return;
            }
            // After several consecutive failures, give up
            if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
                stopPolling('Lost connection to server. Please refresh the page and try again.');
                return;
            }
            // Otherwise keep polling — transient network blip
        }
    }, 5000); // Poll every 5 seconds
}

// Reset the process button and clear selections
function resetProcessButton() {
    const processBtn = document.getElementById('process-btn');
    processBtn.disabled = false;
    processBtn.innerHTML = '<i class="fas fa-magic mr-2"></i>Process Files';
    selectedFiles = [];
    selectedFolders = [];
    displaySelectedFiles();
    const fileInput = document.getElementById('file-input');
    const folderInput = document.getElementById('folder-input');
    if (fileInput) fileInput.value = '';
    if (folderInput) folderInput.value = '';
}

// Handle old-style synchronous response (fallback)
function handleSynchronousResponse(data, filesToProcess, totalFiles) {
    updateModalProgress(100, 'Processing complete!');
    filesToProcess.forEach(item => {
        const name = uploadMode === 'folder' ? item.path : item.name;
        updateFileProgress(name, 'Complete', 100);
    });

    if (data.errors && data.errors.length > 0) {
        const failedNames = data.errors.map(e => {
            const colonIdx = e.indexOf(':');
            return colonIdx > 0 ? e.substring(0, colonIdx).trim() : '';
        });
        window._lastFailedFileObjects = filesToProcess.filter(item => {
            const name = uploadMode === 'folder' ? item.path : item.name;
            return failedNames.some(fn => name === fn || name.includes(fn));
        });
    } else {
        window._lastFailedFileObjects = [];
    }

    if (data.download_url) {
        setTimeout(() => {
            showResultsInModal(data, totalFiles);
            setTimeout(() => {
                triggerDownload(data.download_url);
            }, 500);
        }, 800);
    } else if (data.errors) {
        showResultsInModal(data, totalFiles);
    }

    resetProcessButton();
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
    files.forEach((item, index) => {
        const name = uploadMode === 'folder' ? item.path : item.name;
        const progressItem = createProgressItem(name, index);
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

    // Elapsed time display
    if (data.elapsed_seconds !== undefined && data.elapsed_seconds !== null) {
        html += `
            <div class="bg-indigo-50 p-3 rounded-lg text-center">
                <p class="text-sm text-indigo-800 font-medium">
                    <i class="fas fa-clock mr-1"></i>
                    Completed in ${formatElapsedTime(data.elapsed_seconds)}
                </p>
            </div>
        `;
    }

    if (data.file) {
        // Single file
        html += `
            <div class="bg-green-50 p-4 rounded-lg">
                <h3 class="font-semibold text-green-800 mb-2">File Renamed Successfully</h3>
                <p class="text-sm text-gray-700">
                    <strong>Original:</strong> ${escapeHtml(data.file.original_name)}<br>
                    <strong>New Name:</strong> ${escapeHtml(data.file.new_name)}
                </p>
            </div>
        `;
    } else if (data.files && data.files.length > 0) {
        // Multiple files - compact list
        html += '<h3 class="font-semibold text-gray-900 mb-1">Successfully Renamed Files:</h3>';
        html += '<div class="max-h-48 overflow-y-auto divide-y divide-gray-200">';
        data.files.forEach(file => {
            html += `
                <div class="py-1.5 px-2">
                    <p class="text-xs text-gray-500 truncate">${escapeHtml(file.original_name)}</p>
                    <p class="text-sm text-gray-900 truncate">&rarr; ${escapeHtml(file.new_name)}</p>
                </div>
            `;
        });
        html += '</div>';
    }

    if (data.errors && data.errors.length > 0) {
        // Extract filenames from error messages (format: "filename.pdf: error message")
        const failedFiles = data.errors.map(error => {
            const colonIdx = error.indexOf(':');
            return colonIdx > 0 ? error.substring(0, colonIdx).trim() : error;
        });

        html += `
            <div class="bg-yellow-50 p-4 rounded-lg">
                <h3 class="font-semibold text-yellow-800 mb-2">Errors (${data.errors.length}):</h3>
                <ul class="text-sm text-yellow-700 space-y-1">
                    ${data.errors.map(error => `<li>&bull; ${escapeHtml(error)}</li>`).join('')}
                </ul>
                <button onclick="retryFailedFiles()" class="mt-3 px-4 py-2 bg-yellow-600 text-white text-sm font-medium rounded-lg hover:bg-yellow-700 transition-colors">
                    <i class="fas fa-redo mr-1"></i> Retry Failed Files
                </button>
            </div>
        `;

        // Store failed filenames for retry
        window._lastFailedFiles = failedFiles;
    }

    if (data.download_url) {
        html += `
            <div class="bg-blue-50 p-4 rounded-lg">
                <p class="text-sm text-blue-800">
                    <i class="fas fa-download mr-1"></i>
                    Your download should start automatically. If not,
                    <a href="${escapeHtml(data.download_url)}" class="underline font-semibold">click here</a>.
                </p>
            </div>
        `;
    }

    // Always add a Close button at the bottom right
    html += `
        <div class="flex justify-end mt-4">
            <button id="auto-close-btn" onclick="closeProcessingModal()" class="px-4 py-2 bg-gray-600 text-white text-sm font-medium rounded-lg hover:bg-gray-700 transition-colors">
                <i class="fas fa-times mr-1"></i> Close
            </button>
        </div>
    `;

    html += '</div>';

    content.innerHTML = html;

    // Transition to complete state
    processingState.classList.add('hidden');
    completeState.classList.remove('hidden');

    // Auto-close with countdown if all files succeeded (no errors).
    // Cancel the countdown when the user interacts with the modal so they
    // can read/copy the renamed filenames without time pressure.
    if (!data.errors || data.errors.length === 0) {
        let countdown = 10;
        const closeBtn = document.getElementById('auto-close-btn');
        const modal = document.getElementById('processing-modal');
        if (closeBtn) {
            closeBtn.textContent = `Close (${countdown}s)`;
        }

        const cancelCountdown = () => {
            if (window._autoCloseInterval) {
                clearInterval(window._autoCloseInterval);
                window._autoCloseInterval = null;
            }
            if (closeBtn) {
                closeBtn.innerHTML = '<i class="fas fa-times mr-1"></i> Close';
            }
            // Remove all interaction listeners
            if (modal && window._autoCloseListeners) {
                window._autoCloseListeners.forEach(({type, fn}) => {
                    modal.removeEventListener(type, fn, true);
                });
                window._autoCloseListeners = null;
            }
        };

        // Attach interaction listeners that cancel the countdown
        if (modal) {
            window._autoCloseListeners = [
                {type: 'mousemove', fn: cancelCountdown},
                {type: 'mousedown', fn: cancelCountdown},
                {type: 'keydown', fn: cancelCountdown},
                {type: 'wheel', fn: cancelCountdown},
                {type: 'touchstart', fn: cancelCountdown},
            ];
            window._autoCloseListeners.forEach(({type, fn}) => {
                modal.addEventListener(type, fn, {capture: true, once: true});
            });
        }

        window._autoCloseInterval = setInterval(() => {
            countdown--;
            if (closeBtn) {
                closeBtn.textContent = `Close (${countdown}s)`;
            }
            if (countdown <= 0) {
                cancelCountdown();
                closeProcessingModal();
            }
        }, 1000);
    }
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
            <p class="text-sm text-red-700">${escapeHtml(errorMsg)}</p>
        </div>
    `;

    if (details && details.length > 0) {
        html += `
            <div class="bg-yellow-50 p-4 rounded-lg mt-4">
                <h3 class="font-semibold text-yellow-800 mb-2">Details:</h3>
                <ul class="text-sm text-yellow-700 space-y-1">
                    ${details.map(d => `<li>&bull; ${escapeHtml(d)}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    content.innerHTML = html;

    // Transition to complete state (showing error)
    processingState.classList.add('hidden');
    completeState.classList.remove('hidden');
}

// Retry failed files from last upload
function retryFailedFiles() {
    if (!window._lastFailedFileObjects || window._lastFailedFileObjects.length === 0) {
        showToast('No failed files to retry', 'error');
        return;
    }

    // Close the modal
    closeProcessingModal();

    // Set the failed files as the new selection and trigger processing
    selectedFiles = window._lastFailedFileObjects;
    uploadMode = 'files';
    displaySelectedFiles();
    updateProcessButton();

    // Auto-trigger processing after a short delay
    setTimeout(() => {
        processFiles();
    }, 300);
}

// Close processing modal
function closeProcessingModal() {
    const modal = document.getElementById('processing-modal');
    modal.classList.add('hidden');
    // Show summary stats again for next time
    document.getElementById('summary-stats').classList.remove('hidden');
    // Stop any active polling
    if (_pollingInterval) {
        clearInterval(_pollingInterval);
        _pollingInterval = null;
    }
    // Clear auto-close countdown
    if (window._autoCloseInterval) {
        clearInterval(window._autoCloseInterval);
        window._autoCloseInterval = null;
    }
    // Remove auto-close interaction listeners
    if (window._autoCloseListeners) {
        window._autoCloseListeners.forEach(({type, fn}) => {
            modal.removeEventListener(type, fn, true);
        });
        window._autoCloseListeners = null;
    }
}

// Create progress item for file
// Uses an index-based stable ID to avoid collisions when two filenames
// would normalize to the same string (e.g. "paper(1).pdf" and "paper-1-pdf").
// The fileName itself is stored on the element via dataset for lookup.
function createProgressItem(fileName, index) {
    const div = document.createElement('div');
    div.className = 'flex items-center justify-between p-3 bg-gray-50 rounded-lg progress-item';
    div.id = `progress-${index}`;
    div.dataset.filename = fileName;
    div.innerHTML = `
        <div class="flex items-center flex-1">
            <i class="fas fa-file-pdf text-red-600 mr-3 file-icon"></i>
            <div class="flex-1">
                <p class="font-medium text-gray-900 text-sm">${escapeHtml(fileName)}</p>
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
// Looks up the row by matching dataset.filename (set in createProgressItem).
// We iterate and compare instead of using a CSS attribute selector to avoid
// having to escape arbitrary filename characters (quotes, brackets, etc.) for
// the selector parser.
function updateFileProgress(fileName, status, percent, type = 'success') {
    const items = document.querySelectorAll('#modal-progress-list .progress-item');
    let element = null;
    for (const item of items) {
        if (item.dataset.filename === fileName) {
            element = item;
            break;
        }
    }

    if (!element) return;

    const statusText = element.querySelector('.status-text');
    const progressFill = element.querySelector('.progress-fill');
    const fileIcon = element.querySelector('.file-icon');

    statusText.textContent = status;
    progressFill.style.width = `${percent}%`;

    if (type === 'error') {
        progressFill.className = 'progress-fill bg-red-600 h-2 rounded-full';
        statusText.className = 'text-xs text-red-600 status-text';
        if (fileIcon) {
            fileIcon.className = 'fas fa-times-circle text-red-600 mr-3 file-icon';
        }
    } else if (percent === 100 && type === 'success') {
        progressFill.className = 'progress-fill bg-green-600 h-2 rounded-full';
        statusText.className = 'text-xs text-green-600 status-text';
        if (fileIcon) {
            fileIcon.className = 'fas fa-check-circle text-green-600 mr-3 file-icon';
        }
    }
}


// Load user limits
async function loadUserLimits() {
    try {
        const response = await axios.get('limits');
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
        const response = await axios.get('auth/me');
        currentUser = response.data.user;
        updateAuthUI(currentUser);
        // (Re)initialize inactivity tracking now that we know the user is authenticated.
        // initializeInactivityTracking() is idempotent (resetInactivityTimer clears old timers).
        if (typeof initializeInactivityTracking === 'function') {
            initializeInactivityTracking();
        }
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
                <span class="text-sm text-gray-700">Welcome, <span class="font-semibold">${escapeHtml(user.name)}</span></span>
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

    if (userMenu && !userIcon && !userMenu.contains(event.target)) {
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
        const response = await axios.post('auth/login', {
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
        const response = await axios.post('auth/register', {
            name: name,
            email: email,
            password: password,
            password_confirm: confirmPassword
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
        await axios.post('auth/logout');
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

// Toggle password field visibility
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    const icon = btn.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.replace('fa-eye', 'fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.replace('fa-eye-slash', 'fa-eye');
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
        const response = await axios.post('auth/change-password', {
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
        const response = await axios.get('usage-stats');

        const stats = response.data;

        // Create and show usage stats modal
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl p-6 max-w-2xl w-full mx-4" style="max-height: 80vh; overflow-y: auto;">
                <div class="flex justify-between items-center mb-6">
                    <h3 class="text-2xl font-bold text-gray-900">Your Usage Statistics</h3>
                    <button onclick="closeModal(this)" class="text-gray-400 hover:text-gray-600">
                        <i class="fas fa-times text-xl"></i>
                    </button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                    <div class="text-center p-4 bg-blue-50 rounded-lg">
                        <div class="text-3xl font-bold text-blue-600">${escapeHtml(stats.total_submissions)}</div>
                        <div class="text-sm text-gray-600 mt-1">Total Submissions</div>
                    </div>
                    <div class="text-center p-4 bg-green-50 rounded-lg">
                        <div class="text-3xl font-bold text-green-600">${escapeHtml(stats.total_files_processed)}</div>
                        <div class="text-sm text-gray-600 mt-1">Files Processed</div>
                    </div>
                    <div class="text-center p-4 bg-purple-50 rounded-lg">
                        <div class="text-3xl font-bold text-purple-600">${escapeHtml(stats.max_files_per_submission)}</div>
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
                                        <p class="text-sm font-medium">${escapeHtml(sub.files_processed)} files processed</p>
                                        <p class="text-xs text-gray-500">${new Date(sub.timestamp).toLocaleString()}</p>
                                    </div>
                                    <span class="text-xs text-gray-500">IP: ${escapeHtml(sub.ip_address)}</span>
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
            <span>${escapeHtml(message)}</span>
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
        window.location.href = (window.APP_BASE_URL || '') + '/';
    }
}

// Initialize inactivity tracking when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Wait a short delay to ensure auth status is loaded
    setTimeout(() => {
        initializeInactivityTracking();
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

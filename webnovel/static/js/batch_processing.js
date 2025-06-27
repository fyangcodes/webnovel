document.addEventListener('DOMContentLoaded', function() {
    const checkboxes = document.querySelectorAll('.chapter-checkbox');
    const batchControls = document.getElementById('batch-controls');
    const selectAllBtn = document.getElementById('select-all-btn');
    const deselectAllBtn = document.getElementById('deselect-all-btn');
    const batchModal = new bootstrap.Modal(document.getElementById('batchModal'));
    
    // Show/hide batch controls based on checkbox state
    function updateBatchControls() {
        const checkedBoxes = document.querySelectorAll('.chapter-checkbox:checked');
        batchControls.style.display = checkedBoxes.length > 0 ? 'flex' : 'none';
    }
    
    // Select all chapters
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function() {
            checkboxes.forEach(checkbox => checkbox.checked = true);
            updateBatchControls();
        });
    }
    
    // Deselect all chapters
    if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', function() {
            checkboxes.forEach(checkbox => checkbox.checked = false);
            updateBatchControls();
        });
    }
    
    // Update batch controls when checkboxes change
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateBatchControls);
    });
    
    // Batch analyze with LLM
    const batchAnalyzeBtn = document.getElementById('batch-analyze-btn');
    if (batchAnalyzeBtn) {
        batchAnalyzeBtn.addEventListener('click', function() {
            const selectedChapters = Array.from(document.querySelectorAll('.chapter-checkbox:checked'))
                .map(cb => cb.value);
            
            if (selectedChapters.length === 0) {
                alert('Please select at least one chapter to analyze.');
                return;
            }
            
            // Show confirmation modal
            document.getElementById('batch-modal-content').innerHTML = 
                '<p>You are about to analyze <strong>' + selectedChapters.length + '</strong> chapter(s) with LLM to generate abstracts and key terms.</p>' +
                '<p>This process may take some time. Continue?</p>';
            
            document.getElementById('batch-confirm-btn').onclick = function() {
                // Submit batch analysis request
                fetch('/books/batch-analyze-chapters/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify({
                        chapter_ids: selectedChapters,
                        book_id: window.bookId
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(data.message);
                        location.reload();
                    } else {
                        alert('Error: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred during batch analysis.');
                });
                
                batchModal.hide();
            };
            
            batchModal.show();
        });
    }
}); 
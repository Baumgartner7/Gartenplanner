// Minimal JavaScript for Gartenplanner
// This file contains only essential UI enhancements

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.transition = 'opacity 0.5s';
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 500);
        }, 5000);
    });

    // Set default date for date inputs to today if empty
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        if (!input.value) {
            input.value = new Date().toISOString().split('T')[0];
        }
    });
});
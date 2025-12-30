/**
 * Activity Tracker - Shared JavaScript Utilities
 * This file contains common utility functions used across all pages.
 */

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} text - The text to escape
 * @returns {string} Escaped text safe for HTML insertion
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format duration in seconds to human-readable string
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration (e.g., "45s", "12m", "2h 15m")
 */
function formatDuration(seconds) {
    if (seconds == null || isNaN(seconds)) return '';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    const hours = Math.floor(seconds / 3600);
    const mins = Math.round((seconds % 3600) / 60);
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

/**
 * Format a timestamp to locale time string
 * @param {string|Date} timestamp - ISO timestamp or Date object
 * @param {Object} options - Intl.DateTimeFormat options
 * @returns {string} Formatted time string
 */
function formatTimestamp(timestamp, options = { hour: 'numeric', minute: '2-digit', hour12: true }) {
    const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
    return date.toLocaleTimeString([], options);
}

/**
 * Format a date to locale date string
 * @param {string|Date} date - ISO date string or Date object
 * @param {Object} options - Intl.DateTimeFormat options
 * @returns {string} Formatted date string
 */
function formatDate(date, options = { weekday: 'short', month: 'short', day: 'numeric' }) {
    const d = date instanceof Date ? date : new Date(date);
    return d.toLocaleDateString([], options);
}

/**
 * Get local date string in YYYY-MM-DD format (respecting local timezone)
 * @param {Date} date - Date object
 * @returns {string} Date string in YYYY-MM-DD format
 */
function getLocalDateString(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * Debounce function execution
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(fn, delay = 300) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * Throttle function execution
 * @param {Function} fn - Function to throttle
 * @param {number} limit - Minimum time between executions in milliseconds
 * @returns {Function} Throttled function
 */
function throttle(fn, limit = 100) {
    let inThrottle;
    return function (...args) {
        if (!inThrottle) {
            fn.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ==================== Toast Notifications ====================

// Create toast container if it doesn't exist
function getToastContainer() {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    return container;
}

/**
 * Show a toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type of toast: 'success', 'error', 'warning', 'info'
 * @param {number} duration - Duration in milliseconds (0 for persistent)
 * @returns {HTMLElement} The toast element
 */
function showToast(message, type = 'info', duration = 4000) {
    const container = getToastContainer();

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    // Icon based on type
    const icons = {
        success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        error: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };

    toast.innerHTML = `
        <span class="toast-icon" style="color: var(--${type === 'info' ? 'accent' : type})">${icons[type] || icons.info}</span>
        <span class="toast-message">${escapeHtml(message)}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
        </button>
    `;

    container.appendChild(toast);

    // Auto-dismiss
    if (duration > 0) {
        setTimeout(() => {
            toast.style.animation = 'toast-out 0.3s ease-in forwards';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    return toast;
}

// ==================== Chart.js Utilities ====================

/**
 * Safely destroy a Chart.js instance
 * @param {Chart|null} chart - Chart instance to destroy
 * @returns {null} Always returns null for assignment
 */
function destroyChart(chart) {
    if (chart) {
        try {
            chart.destroy();
        } catch (e) {
            console.warn('Chart destroy failed:', e);
        }
    }
    return null;
}

// ==================== Theme Utilities ====================

// Cache for theme colors
let themeColorsCache = null;
let lastThemeCheck = 0;

/**
 * Get current theme colors for Chart.js
 * @param {boolean} forceRefresh - Force cache refresh
 * @returns {Object} Theme colors object
 */
function getThemeColors(forceRefresh = false) {
    const now = Date.now();
    // Refresh cache every 5 seconds or if forced
    if (themeColorsCache && !forceRefresh && now - lastThemeCheck < 5000) {
        return themeColorsCache;
    }

    const style = getComputedStyle(document.documentElement);
    themeColorsCache = {
        text: style.getPropertyValue('--text').trim(),
        muted: style.getPropertyValue('--muted').trim(),
        border: style.getPropertyValue('--border').trim(),
        surface: style.getPropertyValue('--surface').trim(),
        surface2: style.getPropertyValue('--surface-2').trim(),
        accent: style.getPropertyValue('--accent').trim(),
        accentStrong: style.getPropertyValue('--accent-strong').trim(),
        success: style.getPropertyValue('--success').trim(),
        warning: style.getPropertyValue('--warning').trim(),
        danger: style.getPropertyValue('--danger').trim(),
        bg: style.getPropertyValue('--bg').trim()
    };
    lastThemeCheck = now;
    return themeColorsCache;
}

/**
 * Check if dark mode is active
 * @returns {boolean} True if dark mode is active
 */
function isDarkMode() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

// ==================== Fetch Utilities ====================

/**
 * Fetch JSON data with error handling
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} Parsed JSON response
 * @throws {Error} If request fails or response is not OK
 */
async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: response.statusText }));
        throw new Error(error.error || error.message || 'Request failed');
    }

    return response.json();
}

/**
 * POST JSON data with error handling
 * @param {string} url - URL to post to
 * @param {Object} data - Data to send
 * @returns {Promise<Object>} Parsed JSON response
 */
async function postJSON(url, data) {
    return fetchJSON(url, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

// ==================== DOM Utilities ====================

/**
 * Wait for an element to exist in the DOM
 * @param {string} selector - CSS selector
 * @param {number} timeout - Maximum wait time in milliseconds
 * @returns {Promise<Element>} The found element
 */
function waitForElement(selector, timeout = 5000) {
    return new Promise((resolve, reject) => {
        const element = document.querySelector(selector);
        if (element) {
            resolve(element);
            return;
        }

        const observer = new MutationObserver((mutations, obs) => {
            const element = document.querySelector(selector);
            if (element) {
                obs.disconnect();
                resolve(element);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        setTimeout(() => {
            observer.disconnect();
            reject(new Error(`Element ${selector} not found within ${timeout}ms`));
        }, timeout);
    });
}

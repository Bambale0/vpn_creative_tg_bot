/**
 * VPN Admin Panel JavaScript
 * Handles dashboard functionality, charts, and real-time updates
 */

// Global variables
let systemChart = null;
let vpnChart = null;
let registrationsChart = null;
let incomeChart = null;
let refreshInterval = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    initializeAdminPanel();
});

/**
 * Initialize the admin panel
 */
function initializeAdminPanel() {
    try {
        // Initialize charts
        initCharts();

        // Load initial data
        refreshMetrics();

        // Set up auto-refresh
        setupAutoRefresh();

        // Set up event listeners
        setupEventListeners();

        console.log('Admin panel initialized successfully');
    } catch (error) {
        console.error('Error initializing admin panel:', error);
    }
}

/**
 * Initialize all charts
 */
function initCharts() {
    try {
        // System metrics chart
        const systemCtx = document.getElementById('systemMetricsChart');
        if (systemCtx) {
            systemChart = new Chart(systemCtx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU %',
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        data: [],
                        tension: 0.4
                    }, {
                        label: 'RAM %',
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        data: [],
                        tension: 0.4
                    }, {
                        label: 'Disk %',
                        borderColor: 'rgb(255, 159, 64)',
                        backgroundColor: 'rgba(255, 159, 64, 0.1)',
                        data: [],
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: 'System Metrics'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });
        }

        // VPN metrics chart
        const vpnCtx = document.getElementById('vpnMetricsChart');
        if (vpnCtx) {
            vpnChart = new Chart(vpnCtx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Active Connections',
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        data: [],
                        tension: 0.4
                    }, {
                        label: 'Bandwidth (MB/s)',
                        borderColor: 'rgb(153, 102, 255)',
                        backgroundColor: 'rgba(153, 102, 255, 0.1)',
                        data: [],
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: 'VPN Metrics'
                        }
                    }
                }
            });
        }

        // Registrations chart
        const registrationsCtx = document.getElementById('registrationsChart');
        if (registrationsCtx) {
            registrationsChart = new Chart(registrationsCtx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Регистрации',
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        data: [],
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
        }

        // Income chart
        const incomeCtx = document.getElementById('incomeChart');
        if (incomeCtx) {
            incomeChart = new Chart(incomeCtx.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Доход (₽)',
                        backgroundColor: 'rgb(255, 159, 64)',
                        data: []
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
        }

        console.log('Charts initialized successfully');
    } catch (error) {
        console.error('Error initializing charts:', error);
    }
}

/**
 * Refresh metrics and update charts
 */
async function refreshMetrics() {
    try {
        console.log('Refreshing metrics...');

        // Fetch system metrics
        const sysResp = await fetch('/admin/api/metrics/system');
        const sysData = await sysResp.json();

        // Fetch VPN metrics
        const vpnResp = await fetch('/admin/api/metrics/vpn');
        const vpnData = await vpnResp.json();

        // Fetch stats
        const statsResp = await fetch('/admin/api/stats');
        const statsData = await statsResp.json();

        // Update charts
        updateCharts(sysData.metrics, vpnData.metrics);

        // Update counters
        updateCounters(statsData);

        // Update active connections
        if (vpnData.metrics && vpnData.metrics.length > 0) {
            const latestMetric = vpnData.metrics[vpnData.metrics.length - 1];
            const activeConnections = document.getElementById('active-connections');
            if (activeConnections) {
                activeConnections.textContent = latestMetric[1] || '0'; // active_connections
            }
        }

        console.log('Metrics refreshed successfully');
    } catch (error) {
        console.error('Error refreshing metrics:', error);
        showNotification('Ошибка при обновлении метрик', 'error');
    }
}

/**
 * Update chart data
 */
function updateCharts(systemMetrics, vpnMetrics) {
    try {
        // Update system chart
        if (systemChart && systemMetrics) {
            const labels = systemMetrics.map(item => new Date(item[0]).toLocaleTimeString());
            const cpuData = systemMetrics.map(item => item[1]); // cpu_usage
            const memoryData = systemMetrics.map(item => item[2]); // memory_usage
            const diskData = systemMetrics.map(item => item[3]); // disk_usage

            systemChart.data.labels = labels;
            systemChart.data.datasets[0].data = cpuData;
            systemChart.data.datasets[1].data = memoryData;
            systemChart.data.datasets[2].data = diskData;
            systemChart.update('none');
        }

        // Update VPN chart
        if (vpnChart && vpnMetrics) {
            const labels = vpnMetrics.map(item => new Date(item[0]).toLocaleTimeString());
            const connectionsData = vpnMetrics.map(item => item[1]); // active_connections
            const bandwidthData = vpnMetrics.map(item => (item[2] / 1024 / 1024).toFixed(2)); // bandwidth_usage in MB/s

            vpnChart.data.labels = labels;
            vpnChart.data.datasets[0].data = connectionsData;
            vpnChart.data.datasets[1].data = bandwidthData;
            vpnChart.update('none');
        }
    } catch (error) {
        console.error('Error updating charts:', error);
    }
}

/**
 * Update counter values
 */
function updateCounters(statsData) {
    try {
        // Update total users
        const totalUsersElement = document.querySelector('.stat-card.bg-primary .card-text');
        if (totalUsersElement && statsData.total_users !== undefined) {
            totalUsersElement.textContent = statsData.total_users;
        }

        // Update active subscriptions
        const activeSubsElement = document.querySelector('.stat-card.bg-success .card-text');
        if (activeSubsElement && statsData.active_subs !== undefined) {
            activeSubsElement.textContent = statsData.active_subs;
        }

        // Update total income
        const incomeElement = document.querySelector('.stat-card.bg-warning .card-text');
        if (incomeElement && statsData.income) {
            const totalIncome = (parseFloat(statsData.income.yookassa || 0) +
                parseFloat(statsData.income.crypto || 0));
            incomeElement.textContent = `${totalIncome.toLocaleString()} ₽`;
        }
    } catch (error) {
        console.error('Error updating counters:', error);
    }
}

/**
 * Set up auto-refresh
 */
function setupAutoRefresh() {
    // Refresh every 60 seconds
    refreshInterval = setInterval(refreshMetrics, 60000);
    console.log('Auto-refresh set up (60 seconds)');
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Refresh button
    const refreshBtn = document.querySelector('[onclick="refreshMetrics()"]');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshMetrics);
    }

    // Service restart buttons
    const restartVpnBtn = document.querySelector('[onclick="restartService(\'vpn\')"]');
    if (restartVpnBtn) {
        restartVpnBtn.addEventListener('click', () => restartService('vpn'));
    }

    const restartBotBtn = document.querySelector('[onclick="restartService(\'bot\')"]');
    if (restartBotBtn) {
        restartBotBtn.addEventListener('click', () => restartService('bot'));
    }
}

/**
 * Restart a service
 */
async function restartService(service) {
    try {
        if (!confirm(`Вы уверены, что хотите перезапустить ${service.toUpperCase()}?`)) {
            return;
        }

        const response = await fetch(`/admin/api/system/restart/${service}`, {
            method: 'POST'
        });

        if (response.ok) {
            showNotification(`${service.toUpperCase()} сервис перезапущен`, 'success');
        } else {
            throw new Error('Restart failed');
        }
    } catch (error) {
        console.error(`Error restarting ${service}:`, error);
        showNotification(`Ошибка при перезапуске ${service}`, 'error');
    }
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    try {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Add to body
        document.body.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);

        console.log(`Notification shown: ${message}`);
    } catch (error) {
        console.error('Error showing notification:', error);
    }
}

/**
 * Refresh audit log
 */
async function refreshAuditLog() {
    try {
        const resp = await fetch('/admin/api/system/audit');
        const data = await resp.json();

        // Update audit log table
        const tbody = document.querySelector('#audit-log tbody');
        if (tbody && data.logs) {
            tbody.innerHTML = '';
            data.logs.forEach(log => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${new Date(log[0]).toLocaleString()}</td>
                    <td>${log[1]}</td>
                    <td>${log[2]}</td>
                    <td>${log[3] || 'N/A'}</td>
                `;
                tbody.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Error refreshing audit log:', error);
    }
}

/**
 * Export data
 */
function exportData(format) {
    try {
        window.open(`/admin/api/export/${format}`, '_blank');
        showNotification(`Данные экспортированы в формате ${format.toUpperCase()}`, 'success');
    } catch (error) {
        console.error('Error exporting data:', error);
        showNotification('Ошибка при экспорте данных', 'error');
    }
}

/**
 * Cleanup on page unload
 */
window.addEventListener('beforeunload', function () {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});

// Export functions for use in templates
window.refreshMetrics = refreshMetrics;
window.restartService = restartService;
window.exportData = exportData;
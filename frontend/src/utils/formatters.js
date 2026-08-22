export const formatCurrency = (amount) => {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }).format(amount);
};

export const formatDate = (dateStr) => {
  return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
};

export const formatPercent = (value) => `${(value * 100).toFixed(1)}%`;

export const formatNumber = (num) => new Intl.NumberFormat('en-US').format(num);

export const getRiskLevel = (score) => {
  if (score >= 700) return { label: 'Low Risk', color: 'emerald' };
  if (score >= 550) return { label: 'Moderate Risk', color: 'amber' };
  return { label: 'High Risk', color: 'ruby' };
};

export const getStatusBadge = (status) => {
  const map = {
    'Draft': 'sapphire',
    'Submitted': 'gold',
    'Under Review': 'amber',
    'Approved': 'emerald',
    'Rejected': 'ruby',
    'Disbursed': 'emerald',
  };
  return map[status] || 'gold';
};

export const truncateText = (text, maxLen = 80) => {
  if (text.length <= maxLen) return text;
  return text.substring(0, maxLen) + '…';
};

export const timeAgo = (dateStr) => {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
};

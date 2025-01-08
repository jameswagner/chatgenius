export const formatMessageTimestamp = (timestamp: string): string => {
  const messageDate = new Date(timestamp);
  const today = new Date();
  
  // Set both dates to start of day for comparison
  const messageDay = new Date(messageDate.getFullYear(), messageDate.getMonth(), messageDate.getDate());
  const todayDay = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  
  // Format time (e.g., "2:30 PM")
  const timeString = messageDate.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  });
  
  // If message is from a different day, include the date
  if (messageDay < todayDay) {
    return messageDate.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: messageDay.getFullYear() !== todayDay.getFullYear() ? 'numeric' : undefined
    }) + ' at ' + timeString;
  }
  
  // Same day, just return time
  return timeString;
}; 
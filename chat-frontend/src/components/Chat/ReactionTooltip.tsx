interface ReactionTooltipProps {
  userIds: string[];
  currentUserId: string | null;
  userNames: { [key: string]: string };
  maxDisplay?: number;
}

export const ReactionTooltip = ({ userIds, currentUserId, userNames, maxDisplay = 3 }: ReactionTooltipProps) => {
  const formatUserList = () => {
    // Sort so current user is first
    const sortedIds = [...userIds].sort((a, b) => {
      if (a === currentUserId) return -1;
      if (b === currentUserId) return 1;
      return 0;
    });

    const totalCount = sortedIds.length;
    const displayCount = Math.min(maxDisplay, totalCount);
    const remainingCount = totalCount - displayCount;

    const displayedUsers = sortedIds.slice(0, displayCount).map(id => 
      id === currentUserId ? 'You' : userNames[id]
    );

    if (totalCount === 1) {
      return displayedUsers[0];
    }

    if (totalCount === 2) {
      return `${displayedUsers[0]} and ${displayedUsers[1]}`;
    }

    if (remainingCount === 0) {
      return `${displayedUsers.slice(0, -1).join(', ')} and ${displayedUsers[displayedUsers.length - 1]}`;
    }

    return `${displayedUsers.join(', ')} and ${remainingCount} other${remainingCount === 1 ? '' : 's'}`;
  };

  return (
    <div className="absolute bottom-full mb-1 bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
      {formatUserList()}
    </div>
  );
}; 
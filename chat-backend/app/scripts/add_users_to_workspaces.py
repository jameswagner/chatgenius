from app.services.workspace_service import WorkspaceService
from app.services.channel_service import ChannelService
from app.services.user_service import UserService

# Initialize services
workspace_service = WorkspaceService()
channel_service = ChannelService()
user_service = UserService()

# Get all workspaces
workspaces = workspace_service.get_all_workspaces()

for workspace in workspaces:
    workspace_id = workspace.id
    print(f"Processing workspace: {workspace_id}")
    
    # Get all channels in the workspace
    channels = channel_service.get_workspace_channels(workspace_id)
    
    # Track users already added to the workspace
    added_users = set(workspace_service.get_users_by_workspace(workspace_id))
    
    for channel in channels:
        channel_id = channel.id
        print(f"  Processing channel: {channel_id}")
        
        # Get all users in the channel
        users = channel_service.get_channel_members(channel_id)
        
        for user in users:
            user_id = user['id']
            if user_id not in added_users:
                # Add user to workspace
                workspace_service.add_user_to_workspace(workspace_id, user_id)
                added_users.add(user_id)
                print(f"    Added user {user_id} to workspace {workspace_id}")
            else:
                print(f"    User {user_id} already in workspace {workspace_id}")

print("Completed processing all workspaces.") 
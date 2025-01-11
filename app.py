@app.route('/messages/<message_id>', methods=['PUT'])
@jwt_required()
def update_message(message_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({'error': 'Content is required'}), 400
    
    if 'version' not in data:
        return jsonify({'error': 'Version number is required'}), 400

    try:
        # Get the message from DynamoDB
        message = messages_table.get_item(Key={'id': message_id})
        if 'Item' not in message:
            return jsonify({'error': 'Message not found'}), 404
            
        message = message['Item']
        
        # Verify ownership
        if str(message['user_id']) != str(current_user_id):
            return jsonify({'error': 'You can only edit your own messages'}), 403
        
        # Check version
        if message['version'] != data['version']:
            return jsonify({'error': 'Message has been updated by someone else'}), 409
        
        # Update the message using conditional expression for version check
        try:
            response = messages_table.update_item(
                Key={'id': message_id},
                UpdateExpression='SET content = :content, edited_at = :edited_at, is_edited = :is_edited, version = :new_version',
                ConditionExpression='version = :current_version',
                ExpressionAttributeValues={
                    ':content': data['content'],
                    ':edited_at': datetime.utcnow().isoformat(),
                    ':is_edited': True,
                    ':new_version': message['version'] + 1,
                    ':current_version': message['version']
                },
                ReturnValues='ALL_NEW'
            )
            
            updated_message = response['Attributes']
            
            # Emit WebSocket event
            socketio.emit('message.update', updated_message, room=str(message['channel_id']))
            
            return jsonify(updated_message)
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return jsonify({'error': 'Message was updated by someone else'}), 409
            raise

    except Exception as e:
        print(f"Error updating message: {str(e)}")
        return jsonify({'error': str(e)}), 500 
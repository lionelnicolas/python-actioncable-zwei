"""
ActionCable subscription.
"""

import uuid
import json
import logging

logger = logging.getLogger('actioncable')


class Subscription:
    """
    Subscriptions on a server.
    """
    def __init__(self, connection, identifier, on_event=None):
        """
        :param connection: The connection which is used to subscribe.
        :param identifier: (Optional) Additional identifier information.
        :param on_event: (Optional) Core event callback.
        """
        self.uuid = str(uuid.uuid1())

        self.connection = connection
        self.identifier = identifier
        self.on_event = on_event

        self.receive_callback = None

        self.state = 'unsubcribed'
        self.message_queue = []

        self.logger = logger

        self.connection.subscriptions[self.uuid] = self

    def create(self):
        """
        Subscribes at the server.
        """
        self.logger.debug('Create subscription on server...')

        if not self.connection.connected:
            self.state = 'connection_pending'
            return

        data = {
            'command': 'subscribe',
            'identifier': self._identifier_string()
        }

        self.connection.send(data)
        self._set_state('pending')

    def remove(self):
        """
        Removes the subscription.
        """
        self.logger.debug('Remove subscription from server...')

        data = {
            'command': 'unsubscribe',
            'identifier': self._identifier_string()
        }

        self.connection.send(data)
        self._set_state('unsubscribed')

    def send(self, message):
        """
        Sends data to the server on the
        subscription channel.

        :param data: The JSON data to send.
        """
        self.logger.debug('Send message: {}'.format(message))

        if self.state == 'pending' or self.state == 'connection_pending':
            self.logger.info('Connection not established. Add message to queue.')
            self.message_queue.append(message)
            return
        elif self.state == 'unsubscribed' or self.state == 'rejected':
            self.logger.warning('Not subscribed! Message discarded.')
            return

        data = {
            'command': 'message',
            'identifier': self._identifier_string(),
            'data': message.raw_message()
        }

        self.connection.send(data)

    def on_receive(self, callback):
        """
        Called always if a message is
        received on this channel.

        :param callback: The reference to the callback function.
        """
        self.logger.debug('On receive callback set.')

        self.receive_callback = callback

    def received(self, data):
        """
        API for the connection to forward
        information to this subscription instance.

        :param data: The JSON data which was received.
        :type data: Message
        """
        self.logger.debug('Data received: {}'.format(data))

        message_type = None

        if 'type' in data:
            message_type = data['type']

        if message_type == 'confirm_subscription':
            self._subscribed()
        elif message_type == 'reject_subscription':
            self._rejected()
        elif self.receive_callback is not None and 'message' in data:
            self.receive_callback(data['message'])
        else:
            self.logger.warning('Message type unknown. ({})'.format(message_type))

    def _on_event(self, event, data=None):
        """
        Called to report core events to parent
        """

        if self.on_event is None:
            return

        self.on_event(event, data)

    def _subscribed(self):
        """
        Called when the subscription was
        accepted successfully.
        """
        self.logger.debug('Subscription confirmed.')
        self._set_state('subscribed')
        for message in self.message_queue:
            self.send(message)

    def _rejected(self):
        """
        Called if the subscription was
        rejected by the server.
        """
        self.logger.warning('Subscription rejected.')
        self._set_state('rejected')
        self.message_queue = []

    def _set_state(self, state):
        """Set state attribute"""

        self.state = state
        self._on_event(state)

    def _identifier_string(self):
        return json.dumps(self.identifier)

"""Factory classes for test data generation.

Example factory pattern for Django models:

    import factory
    from factory.django import DjangoModelFactory
    from faker import Faker

    fake = Faker()

    class NotificationFactory(DjangoModelFactory):
        '''Factory for Notification model.'''

        class Meta:
            model = 'core.Notification'

        recipient = factory.LazyAttribute(lambda _: fake.email())
        message = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=200))
        type = factory.Iterator(['email', 'sms', 'push'])
        status = 'pending'

Add your factories here as Django models are created.
"""

from faker import Faker

fake = Faker()

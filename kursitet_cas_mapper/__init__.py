"""
Beyond the original function of CAS attribute mapper, this should also manage other objects...
""" 

# Note: In production this is supposed to be https.
# I'm not even sure how to test that correctly without it...
CAS_URI = 'https://kursitet.ru/cas'

NSMAP = {'cas': CAS_URI}
CAS = '{%s}' % CAS_URI

from django.core.exceptions import ObjectDoesNotExist

def populate_user(user, authentication_response):
    if authentication_response.find(CAS + 'authenticationSuccess/'  + CAS + 'attributes'  , namespaces=NSMAP) is not None:
        attr = authentication_response.find(CAS + 'authenticationSuccess/'  + CAS + 'attributes'  , namespaces=NSMAP)

        if attr.find(CAS + 'is_staff', NSMAP) is not None:
            user.is_staff = attr.find(CAS + 'is_staff', NSMAP).text.upper() == 'TRUE'

        if attr.find(CAS + 'is_superuser', NSMAP) is not None:
            user.is_superuser = attr.find(CAS + 'is_superuser', NSMAP).text.upper() == 'TRUE'

        if attr.find(CAS + 'givenName', NSMAP) is not None:
            user.first_name = attr.find(CAS + 'givenName', NSMAP).text

        if attr.find(CAS + 'sn', NSMAP) is not None:
            user.last_name = attr.find(CAS + 'sn', NSMAP).text

        if attr.find(CAS + 'email', NSMAP) is not None:
            user.email = attr.find(CAS + 'email', NSMAP).text
        
        # Here we handle things that go into UserProfile instead.
        
        # This is a dirty hack and you shouldn't do that. 
        # However, I don't think it's going to work when imported outside of the function body.
        
        from student.models import UserProfile
        
        try:
            user_profile = UserProfile.objects.get(user=user)
        except ObjectDoesNotExist:
            user_profile = UserProfile(user=user)
            
        # There should be more variables, but let's settle on the actual model first.
        if attr.find(CAS + 'fullName', NSMAP) is not None:
            user_profile.name = attr.find(CAS + 'fullName', NSMAP).text
    
        # Profile is always getting saved, just like the user,
        # but the user is getting saved by django_cas.
        user_profile.save()
        
    pass

"""
Beyond the original function of CAS attribute mapper, this should also manage other objects...
""" 

CAS_URI = 'http://www.yale.edu/tp/cas'

NSMAP = {'cas': CAS_URI}
CAS = '{%s}' % CAS_URI

import json

def populate_user(user, authentication_response):
    if authentication_response.find(CAS + 'authenticationSuccess/'  + CAS + 'attributes'  , namespaces=NSMAP) is not None:
        attr = authentication_response.find(CAS + 'authenticationSuccess/'  + CAS + 'attributes'  , namespaces=NSMAP)

        if attr.find(CAS + 'is_staff', NSMAP) is not None:
            user.is_staff = attr.find(CAS + 'is_staff', NSMAP).text.upper() == 'TRUE'

        if attr.find(CAS + 'is_superuser', NSMAP) is not None:
            user.is_superuser = attr.find(CAS + 'is_superuser', NSMAP).text.upper() == 'TRUE'

        if attr.find(CAS + 'is_active', NSMAP) is not None:
            user.is_active = attr.find(CAS + 'is_active', NSMAP).text.upper() == 'TRUE'

        # Limiting by maximum lengths.
        # Max length of firstname/lastname is 30.
        # Max length of a email is 75.
        if attr.find(CAS + 'givenName', NSMAP) is not None:
            user.first_name = attr.find(CAS + 'givenName', NSMAP).text[0:30]

        if attr.find(CAS + 'sn', NSMAP) is not None:
            user.last_name = attr.find(CAS + 'sn', NSMAP).text[0:30]

        if attr.find(CAS + 'email', NSMAP) is not None:
            user.email = attr.find(CAS + 'email', NSMAP).text[0:75]
        
        # Here we handle things that go into UserProfile instead.
        
        # This is a dirty hack and you shouldn't do that. 
        # However, I don't think it's going to work when imported outside of the function body.
        
        from student.models import UserProfile
        
        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user.save()
            user_profile = UserProfile(user=user)
            
        # There should be more variables, but let's settle on the actual model first.
        if attr.find(CAS + 'fullName', NSMAP) is not None:
            user_profile.name = attr.find(CAS + 'fullName', NSMAP).text
    
        # Profile is always getting saved, just like the user,
        # but the user is getting saved by django_cas.
        user_profile.save()

        # Now the really fun bit. Signing the user up for courses given.
        
        coursetag = attr.find(CAS + 'courses', NSMAP)
        if coursetag is not None:
            try:
                courses = json.loads(coursetag.text)
                assert isinstance(courses,list)
            except (ValueError, AssertionError):
                # We failed to parse the tag and get a list, so we leave.
                return
            # We got a list, so we need to import the enroll call.
            from student.models import CourseEnrollment
            from opaque_keys.edx.locator import CourseLocator
            for course in courses:
                if course:
                    # Notice that we don't check if a course by that ID actually exists!
                    # We don't really have the time for this, 
                    # (I seriously suspect this function is getting called more often than once per login)
                    # and CourseEnrollment objects do no checking of their own.
                    # Being enrolled in a deleted course should not be an issue though...
                    org, course, run = course.split('/')
                    CourseEnrollment.enroll(user,CourseLocator(org=org,course=course,run=run))
        
    pass

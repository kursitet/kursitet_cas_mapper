"""
Beyond the original function of CAS attribute mapper, this should also manage other objects...
"""

CAS_URI = 'http://www.yale.edu/tp/cas'

NSMAP = {'cas': CAS_URI}
CAS = '{%s}' % CAS_URI

import json

def populate_user(user, authentication_response):

    attr = authentication_response.find(CAS + 'authenticationSuccess/'  + CAS + 'attributes'  , namespaces=NSMAP)

    if attr is not None:

        staff_flag = attr.find(CAS + 'is_staff', NSMAP)
        if staff_flag is not None:
            user.is_staff = (staff_flag.text or '').upper() == 'TRUE'

        superuser_flag = attr.find(CAS + 'is_superuser', NSMAP)
        if superuser_flag is not None:
            user.is_superuser = (superuser_flag.text or '').upper() == 'TRUE'

        active_flag = attr.find(CAS + 'is_active', NSMAP)
        if active_flag is not None:
            user.is_active = (active_flag.text or '').upper() == 'TRUE'

        # Limiting by maximum lengths.
        # Max length of firstname/lastname is 30.
        # Max length of a email is 75.

        first_name = attr.find(CAS + 'givenName', NSMAP)
        if first_name is not None:
            user.first_name = (first_name.text or '')[0:30]

        last_name = attr.find(CAS + 'sn', NSMAP)
        if last_name is not None:
            user.last_name = (last_name.text or '')[0:30]

        email = attr.find(CAS + 'email', NSMAP)
        if email is not None:
            user.email = (email.text or '')[0:75]

        # Here we handle things that go into UserProfile instead.

        # This is a dirty hack and you shouldn't do that.
        # However, I don't think it's going to work when imported outside of the function body.

        from student.models import UserProfile

        # We don't do that on old edX because it's so bloody fragile.
        # On the new edX, logging in through CAS will also mean an unusable
        # password inside.
        user.set_unusable_password()
        user.save()
        
        # If the user doesn't yet have a profile, it means it's a new one and we need to create it a profile.
        # but we need to save the user first.
        if not UserProfile.objects.filter(user=user):
            user_profile = UserProfile(user=user, name=user.username)
        else:
            user_profile = UserProfile.objects.get(user=user)

        # There should be more variables, but let's settle on the actual model first.
        full_name = attr.find(CAS + 'fullName', NSMAP)
        if full_name is not None:
            user_profile.name = full_name.text or ''
            
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
                    CourseEnrollment.enroll(user,CourseLocator(org=org,course=course,run=run,deprecated=True))

    pass

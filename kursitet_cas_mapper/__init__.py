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
        user_profile, created = UserProfile.objects.get_or_create(user=user, defaults={'name':user.username})

        # There should be more variables, but let's settle on the actual model first.
        full_name = attr.find(CAS + 'fullName', NSMAP)
        if full_name is not None:
            user_profile.name = full_name.text or ''
            
        user_profile.save()

        # Now the really fun bit. Signing the user up for courses given.

        coursetag = attr.find(CAS + 'courses', NSMAP)
        # We also unsubscribe people from courses here the same way.
        anticoursetag = attr.find(CAS + 'unsubscribed_courses', NSMAP)

        from student.models import CourseEnrollment, CourseEnrollmentAllowed
        from opaque_keys.edx.locator import CourseLocator
        from xmodule.modulestore.django import modulestore
        from xmodule.modulestore.exceptions import ItemNotFoundError

        if coursetag is not None:
            try:
                courses = json.loads(coursetag.text)
                assert isinstance(courses,list)
            except (ValueError, AssertionError):
                # We failed to parse the tag and get a list, so we leave.
                return
            # We got a list, so we need to import the enroll call.
            for course in courses:
                if course:
                    locator = CourseLocator.from_string(course)
                    try:
                        course = modulestore().get_course(locator)
                    except ItemNotFoundError:
                        continue
                    CourseEnrollment.enroll(user,locator)
        
        if anticoursetag is not None:
            try:
                anticourses = json.loads(anticoursetag.text)
                assert isinstance(anticourses,list)
            except (ValueError, AssertionError):
                return
            
            # TODO: I need a more sensible way to parse either tag separately and only import if required.
            for course in anticourses:
                if course:
                    locator = CourseLocator.from_string(course)
                    try:
                        course = modulestore().get_course(locator)
                    except ItemNotFoundError:
                        continue
                    CourseEnrollment.unenroll(user,locator)
                    
        # Now implement CourseEnrollmentAllowed objects, because otherwise they will only ever fire when
        # users click a link in the registration email -- which can never happen here.
        if created:
            for cea in CourseEnrollmentAllowed.objects.filter(email=user.email, auto_enroll=True):
                    CourseEnrollment.enroll(user, cea.course_id)

    pass

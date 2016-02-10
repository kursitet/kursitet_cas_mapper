"""
Beyond the original function of CAS attribute mapper, this should also manage other objects...
"""

CAS_URI = 'http://www.yale.edu/tp/cas'

NSMAP = {'cas': CAS_URI}
CAS = '{%s}' % CAS_URI

import json
import logging

log = logging.getLogger(__name__)

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

        from student.models import CourseEnrollment
        from opaque_keys.edx.locator import CourseLocator
        from opaque_keys import InvalidKeyError
        from xmodule.modulestore.django import modulestore
        from xmodule.modulestore.exceptions import ItemNotFoundError

        if coursetag is not None:
            try:
                courses = json.loads(coursetag.text)
                assert isinstance(courses,list)
            except (ValueError, AssertionError):
                # We failed to parse the tag and get a list, so we leave.
                log.error("Course list failed to parse.")
                return

            # We got a list. Compare it to existing enrollments.
            existing_enrollments = CourseEnrollment.objects.filter(user=user, is_active=True).values_list('course_id',flat=True)

            for course in courses:
                if course and not course in existing_enrollments:
                    try:
                        locator = CourseLocator.from_string(course)
                    except (InvalidKeyError, AttributeError) as e:
                        log.error("Invalid course identifier {}".format(course))
                        continue
                    try:
                        course = modulestore().get_course(locator)
                    except ItemNotFoundError:
                        log.error("Course {} does not exist.".format(course))
                        continue
                    CourseEnrollment.enroll(user,locator)
            # Now we need to unsub the user from courses for which they are not enrolled.
            for course in existing_enrollments:
                if not course in courses:
                    try:
                        locator = CourseLocator.from_string(course)
                    except (InvalidKeyError, AttributeError) as e:
                        log.error("Invalid course identifier {} in existing enrollments.".format(course))
                        continue
                    CourseEnrollment.unenroll(user, locator)

        # Now implement CourseEnrollmentAllowed objects, because otherwise they will only ever fire when
        # users click a link in the registration email -- which can never happen here.
        # Considering the new setup, I doubt this will ever be useful.
        if created:
            from student.models import CourseEnrollmentAllowed
            for cea in CourseEnrollmentAllowed.objects.filter(email=user.email, auto_enroll=True):
                    CourseEnrollment.enroll(user, cea.course_id)

        # Now, deal with course administration packets.
        course_admin_tag = attr.find(CAS + 'course_administration_update', NSMAP)

        if course_admin_tag is not None:
            try:
                courses = json.loads(course_admin_tag.text)
                assert isinstance(courses,dict)
            except (ValueError, AssertionError):
                # We failed to parse the tag, so we leave.
                log.error("Could not parse course administration block: <<{}>>".format(course_admin_tag.text))
                return

            from instructor.access import list_with_level, allow_access, revoke_access
            from django_comment_common.models import Role, FORUM_ROLE_ADMINISTRATOR, FORUM_ROLE_MODERATOR, FORUM_ROLE_COMMUNITY_TA
            from django.contrib.auth.models import User

            for course_id, admin_block in courses.iteritems():
                try:
                    locator = CourseLocator.from_string(course_id)
                except (InvalidKeyError, AttributeError) as e:
                    log.error("Invalid course identifier {}".format(course_id))
                    continue
                try:
                    course = modulestore().get_course(locator)
                except ItemNotFoundError:
                    log.error("Course {} does not exist.".format(course_id))
                    continue

                if not course:
                    continue

                # Course roles are relatively easy.
                for block_name, role in [('admin','instructor'), ('staff','staff'), ('beta','beta')]:
                    role_list = admin_block.get(block_name,[])
                    existing = list_with_level(course,role)

                    for username in role_list:
                        try:
                            user = User.objects.get(username=username)
                        except User.DoesNotExist:
                            continue
                        if not user in existing:
                            allow_access(course, user, role)
                            try:
                                CourseEnrollment.enroll(user, locator)
                            except:
                                pass
                    for user in existing:
                        if not user.username in role_list:
                            revoke_access(course, user, role)

                # Forum roles, considerably different.

                for block_name, rolename in [('forum_admin',FORUM_ROLE_ADMINISTRATOR), ('forum_moderator',FORUM_ROLE_MODERATOR), ('forum_assistant',FORUM_ROLE_COMMUNITY_TA)]:
                    role_list = admin_block.get(block_name,[])
                    try:
                        role = Role.objects.get(course_id=locator, name=rolename)
                    except Role.DoesNotExist:
                        continue
                    existing = role.users.all()

                    for user in existing:
                        if not user.username in role_list:
                            role.users.remove(user)
                    for username in role_list:
                        try:
                            user = User.objects.get(username=username)
                        except User.DoesNotExist:
                            continue
                        if not user in existing:
                            role.users.add(user)
                            try:
                                CourseEnrollment.enroll(user, locator)
                            except:
                                pass

    pass

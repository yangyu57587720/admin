from stark.service.stark import site, ModelStark
from django.utils.safestring import mark_safe
from django.shortcuts import redirect, render, HttpResponse
from django.http import JsonResponse
from django.db.models import Q
from django.conf.urls import url
from .models import *
import datetime


class DepartConfig(ModelStark):
    # 部门详细
    list_display = ["title", "code"]


site.register(Department, DepartConfig)


class UserConfig(ModelStark):
    # 员工信息详情表
    list_display = ["name", "email", "depart"]


site.register(UserInfo, UserConfig)


class ClassConfig(ModelStark):
    # 增加班级表显示详情
    def display_classname(self, obj=None, header=False):
        if header:
            return "班级名称"
        class_name = "%s(%s)" % (obj.course.name, str(obj.semester))
        return class_name
    list_display = [display_classname, "tutor", "teachers"]


site.register(ClassList, ClassConfig)


class CusotmerConfig(ModelStark):
    # 取性别的方法
    def display_gender(self, obj=None, header=False):
        if header:
            return "性别"
        return obj.get_gender_display()

    def display_course(self, obj=None, header=False):
        if header:
            return "咨询课程"
        temp = []
        for course in obj.course.all():
            s = "<a href='/stark/app01/customer/cancel_course/%s/%s' style='border: 1px solid #369;padding: 3px 6px;'><span>%s</span></a>&nbsp;" % (obj.pk, course.id, course.name)
            temp.append(s)
        return mark_safe("".join(temp))

    # 自定义创建新增url删除方法
    def cancel_course(self, request, customer_id, course_id):
        obj = Customer.objects.filter(pk=customer_id).first()
        obj.course.remove(course_id)
        return redirect(self.get_list_url())

    def public_customer(self, request):
        # 公共客户资源
        now = datetime.datetime.now()
        delta_day3 = datetime.timedelta(days=3)
        delta_day15 = datetime.timedelta(days=15)
        user_id = 15
        # 在客户表中过滤销售人员三天不处理并且15天没谈妥的单子，排除接受过单子的销售
        customer_list = Customer.objects.filter(Q(last_consult_date__lt=now-delta_day3)|Q(recv_date__lt=now-delta_day15), status=2).exclude(consultant=user_id)
        return render(request, "public.html", locals())

    def further(self, request, customer_id):
        # 获取公共客户资源
        user_id = 11   # request.session.get("user_id)应该去session取当前登录用户
        now = datetime.datetime.now()
        delta_day3 = datetime.timedelta(days=3)
        delta_day15 = datetime.timedelta(days=15)
        # 为该客户更改课程顾问和对应时间
        ret = Customer.objects.filter(pk=customer_id).filter(Q(last_consult_date__lt=now-delta_day3)|Q(recv_date__lt=now-delta_day15), status=2).update(consultant=user_id, last_consult_date=now, recv_date=now)
        if not ret:    # 如果不为空，表示正在跟进
            return HttpResponse("已经被跟进了")
        # 查询更新数据
        CustomerDistrbute.objects.filter(customer_id=customer_id, consultant=user_id, date=now, status=1)
        return HttpResponse("跟进成功")

    def mycustomer(self, request):
        # 个人与客户跟进页面
        user_id = 11
        customer_distrbute_list = CustomerDistrbute.objects.filter(pk=user_id)
        return render(request, "mycustomer.html", locals())

    # 自定义创建新增url路径
    def extra_url(self):
        temp = []
        temp.append(url(r"cancel_course/(\d+)/(\d+)", self.cancel_course))
        temp.append(url(r"public", self.public_customer))
        temp.append(url(r"further/(\d+)", self.further))
        temp.append(url(r"mycustomer/", self.mycustomer))
        return temp

    list_display = ["name", display_gender, display_course, "consultant"]

site.register(Customer, CusotmerConfig)


class ConsultConfig(ModelStark):
    # 客户跟进详细
    list_display = ["customer", "consultant", "date", "note"]


site.register(ConsultRecord, ConsultConfig)


class StudentConfig(ModelStark):
    # 学生表详细
    def score_view(self, request, sid):
        if request.is_ajax():
            sid = request.GET.get("sid")
            cid = request.GET.get("cid")
            # 当前学生的当前班级所有记录
            study_record_list = StudyRecord.objects.filter(student=sid, course_record__class_obj=cid)
            data_list = []
            for study_record in study_record_list:
                day_num = study_record.course_record.day_num
                data_list.append(["day%s" % day_num, study_record.score])
            return JsonResponse(data_list, safe=False)
        else:
            student = Student.objects.filter(pk=sid).first()
            class_list = student.class_list.all()
            return render(request, "score_view.html", locals())

    def extra_url(self):
        # 拼接url
        temp = []
        temp.append(url(r"score_view/(\d+)", self.score_view))
        return temp

    def score_show(self, obj=None, header=False):
        if header:
            return "查看成绩"
        return mark_safe("<a href='/stark/app01/student/score_view/%s'>查看成绩</a>" % obj.pk)

    list_display = ["customer", "class_list", score_show]
    list_display_links = ["customer"]


site.register(Student, StudentConfig)


class CourseRecordConfig(ModelStark):
    # 上课记录详细
    def score(self, request, course_record_id):
        if request.method == "POST":
            data = {}
            for key, value in request.POST.items():
                if key == "csrfmiddlewaretoken":continue
                field, pk = key.rsplit("_", 1)
                if pk in data:
                    data[pk][field] = value
                else:
                    data[pk] = {field: value}
            for pk, update_data in data.items():
                StudyRecord.objects.filter(pk=pk).update(**update_data)
            return redirect(request.path)
        else:
            study_record_list = StudyRecord.objects.filter(course_record=course_record_id)
            score_choices = StudyRecord.score_choices
            return render(request, "score.html", locals())

    def extra_url(self):
        # 拼接url
        temp = []
        temp.append(url(r"record_score/(\d+)", self.score))
        return temp

    def record(self, obj=None, header=False):
        # 不同班级分页
        if header:
            return "学习记录"
        return mark_safe("<a href='/stark/app01/studyrecord/?course_record=%s'>班级详情</a>" % obj.pk)

    def record_score(self, obj=None, header=False):
        # 不同班级分页录入考勤
        if header:
            return "录入考勤"
        return mark_safe("<a href='record_score/%s'>录入成绩</a>" % obj.pk)

    list_display = ["class_obj", "day_num", "teacher", record, record_score]

    def patch_studyrecord(self, request, queryset):
        temp = []
        # queryset课程记录
        for course_record in queryset:
            # 从学生表找到和班级表关联的学生上课记录表(记录了学生总数)
            student_list = Student.objects.filter(class_list__id=course_record.class_obj.pk)
            for student in student_list:
                obj = StudyRecord(student=student, course_record=course_record)
                temp.append(obj)
        StudyRecord.objects.bulk_create(temp)
    patch_studyrecord.short_description = "批量生成学习记录"
    actions = [patch_studyrecord]


site.register(CourseRecord, CourseRecordConfig)


class StudyConfig(ModelStark):
    # 学生详细
    list_display = ["student", "course_record", "record", "score"]

    def patch_late(self, request, queryset):
        queryset.update(record="late")
    patch_late.short_description = "迟到"
    actions = [patch_late]


site.register(StudyRecord, StudyConfig)

site.register(School)
site.register(Course)
site.register(CustomerDistrbute)





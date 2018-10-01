from django.conf.urls import url
from django.shortcuts import render, redirect
from django.db.models.fields.related import ManyToManyField, ForeignKey
from django.urls import reverse
from django.utils.safestring import mark_safe
from stark.utils.page import Pagination
from django.db.models import Q
import copy


class ShowList(object):
    def __init__(self, config, data_list, request):
        self.config = config  # ShowList(self, data_list, request)
        self.data_list = data_list
        # 分页
        self.request = request
        data_count = self.data_list.count()
        current_page = int(self.request.GET.get("page", 1))
        base_path = self.request.path
        self.pagination = Pagination(current_page, data_count, base_path, self.request.GET, per_page_num=8,
                                     pager_count=11, )
        self.page_data = self.data_list[self.pagination.start:self.pagination.end]
        # actions
        self.actions = self.config.new_actions()

    def get_filter_linktags(self):
        link_dic = {}

        for filter_field in self.config.list_filter:
            params = copy.deepcopy(self.request.GET)
            cid = self.request.GET.get(filter_field, 0)
            filter_field_obj = self.config.model._meta.get_field(filter_field)
            if isinstance(filter_field_obj, ForeignKey) or isinstance(filter_field_obj, ManyToManyField):
                data_list = filter_field_obj.rel.to.objects.all()
            else:
                data_list = self.config.model.objects.all().values("pk", filter_field)
            temp = []

            # 处理全部标签
            if params.get(filter_field):
                del params[filter_field]
                temp.append("<a href='?%s'>全部</a>" % params.urlencode())
            else:
                temp.append("<a class='active' href=''>全部</a>")
            # 处理数据标签
            for obj in data_list:
                if isinstance(filter_field_obj, ForeignKey) or isinstance(filter_field_obj, ManyToManyField):
                    pk = obj.pk
                    text = str(obj)
                    params[filter_field] = pk
                else:
                    pk = obj.get("pk")
                    text = obj.get(filter_field)
                    params[filter_field] = text

                _url = params.urlencode()
                if cid == str(pk) or cid == text:
                    link_tag = "<a class='active' href='?%s'>%s</a>" % (_url, text)
                else:
                    link_tag = "<a href='?%s'>%s</a>" % (_url, text)
                temp.append(link_tag)
            link_dic[filter_field] = temp
        return link_dic

    # 批量初始化
    def get_action_list(self):
        temp = []
        for action in self.actions:
            temp.append({
                "name": action.__name__,
                "desc": action.short_description
            })
        return temp

    def get_header(self):
        # 构建表头
        header_list = []
        for field in self.config.new_list_play():
            if callable(field):  # 当前字段可调用
                val = field(self.config, header=True)
                header_list.append(val)
            else:
                if field == "__str__":  # 有__str__返回值直接调用，并大写
                    header_list.append(self.config.model._meta.model_name.upper())
                else:  # 没有就格式化表头名称
                    val = self.config.model._meta.get_field(field).verbose_name
                    header_list.append(val)
        return header_list

    def get_body(self):
        # 构建表单数据
        new_data_list = []
        for obj in self.page_data:
            temp = []
            for filed in self.config.new_list_play():  # ["__str__"]
                if callable(filed):  # 是函数
                    val = filed(self.config, obj)
                else:
                    try:  # 排除["__str__"]报错
                        field_obj = self.config.model._meta.get_field(filed)
                        if isinstance(field_obj, ManyToManyField):
                            ret = getattr(obj, filed).all()
                            t = []
                            for mobj in ret:  # 命名不能重复
                                t.append(str(mobj))
                            val = ",".join(t)
                        else:
                            if field_obj.choices:
                                # 当前字段有choices方法就反射取值
                                val = getattr(obj, "get_"+filed+"_display")
                            else:
                                val = getattr(obj, filed)  # obj获取字符串field的属性值
                            if filed in self.config.list_display_links:  # 当前字段可跳转
                                _url = self.config.get_change_url(obj)
                                val = mark_safe("<a href='%s'>%s</a>" % (_url, val))
                    except Exception as e:  # 接收 ["__str__"]处理
                        val = getattr(obj, filed)
                temp.append(val)
            new_data_list.append(temp)
        return new_data_list


class ModelStark(object):
    list_display = ["__str__", ]  # 当前传递的定制显示的字段
    list_display_links = []  # 当前可以点击跳转的定制字段
    modelform_class = None  # 默认自定制样式类为空
    search_fields = []  # 搜索字段默认为空
    actions = []  # 批量初始化默认为空
    list_filter = []  # 搜索字段默认为空

    def __init__(self, model, site):
        self.model = model  # 当前数据表
        self.site = site  # 指向当前类本身

    # 批量删除
    def patch_delete(self, request, queryset):
        queryset.delete()

    patch_delete.short_description = "批量删除"

    # 表头编辑
    def edit(self, obj=None, header=False):
        if header:
            return "操作"
        _url = self.get_change_url(obj)
        return mark_safe("<a href='%s'>编辑</a>" % _url)

    # 表头删除
    def deletes(self, obj=None, header=False):
        if header:
            return "操作"
        _url = self.get_delete_url(obj)
        return mark_safe("<a href='%s'>删除</a>" % _url)

    # 表头复选框
    def checkbox(self, obj=None, header=False):
        if header:
            return mark_safe('<input id="choice" type="checkbox">')
        return mark_safe('<input class="choice_item" type="checkbox" name="selected_pk" value="%s">' % obj.pk)

    # 判断用户是否自定制样式
    def get_modelform_class(self):
        if not self.modelform_class:
            from django.forms import ModelForm

            class ModelFormDemo(ModelForm):  # 传了就用当前定制样式类
                class Meta:
                    model = self.model
                    fields = "__all__"
                    labels = {""}

            return ModelFormDemo
        else:
            return self.modelform_class  # 没传用默认样式类

    def get_new_form(self, form):
        # 点击 + 号的url
        for bfield in form:
            from django.forms.models import ModelChoiceField
            # 字段类型对象bfield.field
            if isinstance(bfield.field, ModelChoiceField):
                bfield.is_pop = True
                related_model_name = bfield.field.queryset.model._meta.model_name
                related_app_label = bfield.field.queryset.model._meta.app_label
                _url = reverse("%s_%s_add" % (related_app_label, related_model_name))
                # 字段名（字符串）bfield.name
                bfield.url = _url + "?pop_res_id=id_%s" % bfield.name
        return form

    # 增加页面
    def add_view(self, request):
        ModelFormDemo = self.get_modelform_class()
        form = ModelFormDemo()
        for bfield in form:  # 进入父类查找字段
            from django.forms.models import ModelChoiceField  # 进源码找(self.field, self.queryset)
            if isinstance(bfield.field, ModelChoiceField):  # 判断是否是一对多,多对多字段
                # 如果参数bfield.field是ModelChoiceField的实例,或者bfield.field是ModelChoiceField类的子类的一个实例,返回True
                bfield.is_pop = True
                related_model_name = bfield.field.queryset.model._meta.model_name
                related_app_label = bfield.field.queryset.model._meta.app_label
                _url = reverse("%s_%s_add" % (related_app_label, related_model_name))  # url反向解析
                bfield.url = _url + "?pop_res_id=id_%s" % bfield.name  # 生成url
        if request.method == "POST":
            form = ModelFormDemo(request.POST)
            if form.is_valid():
                obj = form.save()
                pop_res_id = request.GET.get("pop_res_id")  # 获取子添加url的值
                if pop_res_id:
                    res = {"pk": obj.pk, "text": str(obj), "pop_res_id": pop_res_id}
                    return render(request, "pop.html", {"res": res})  # 返回用户添加完成的数据
                else:
                    return redirect(self.get_list_url())
        return render(request, "add_view.html", locals())

    # 删除页面
    def delete_view(self, request, id):
        url = self.get_list_url()
        if request.method == "POST":
            self.model.objects.filter(pk=id).delete()
            return redirect(url)
        return render(request, "delete_view.html", locals())

    #  修改页面
    def change_view(self, request, id):
        ModelFormDemo = self.get_modelform_class()
        edit_obj = self.model.objects.filter(pk=id).first()
        if request.method == "POST":
            form = ModelFormDemo(request.POST, instance=edit_obj)
            if form.is_valid():
                form.save()
                return redirect(self.get_list_url())
            return render(request, "add_view.html", locals())
        form = ModelFormDemo(instance=edit_obj)
        form = self.get_new_form(form)
        return render(request, "change_view.html", locals())

    # 表的表头HTML标签和表单数据
    def new_list_play(self):
        temp = []
        temp.append(ModelStark.checkbox)  # 添加当前类的复选框
        temp.extend(self.list_display)  # 扩展当前定制显示的列
        if not self.list_display_links:  # 没有可以点击跳转的定制列
            temp.append(ModelStark.edit)  # 添加当前类的编辑表头
        temp.append(ModelStark.deletes)  # 有就添加当前类的删除表头
        return temp

    # 新的actions返回值
    def new_actions(self):
        temp = []
        temp.append(ModelStark.patch_delete)
        temp.extend(self.actions)
        return temp

    # 获得修改路径
    def get_change_url(self, obj):
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label
        _url = reverse("%s_%s_change" % (app_label, model_name), args=(obj.pk,))
        return _url

    # 获得删除路径
    def get_delete_url(self, obj):
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label
        _url = reverse("%s_%s_delete" % (app_label, model_name), args=(obj.pk,))
        return _url

    # 获得增加路径
    def get_add_url(self):
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label
        _url = reverse("%s_%s_add" % (app_label, model_name))
        return _url

    # 获得当前显示页面url
    def get_list_url(self):
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label
        _url = reverse("%s_%s_list" % (app_label, model_name))
        return _url

    def get_serach_condtion(self, request):
        # 获取serach的Q对象
        key_word = request.GET.get("q", "")
        self.key_word = key_word
        search_connection = Q()
        if key_word:
            search_connection.connector = "or"
            for search_field in self.search_fields:
                search_connection.children.append((search_field + "__contains", key_word))
        return search_connection

    def get_filter_condition(self, request):
        # 获取filter构建Q对象
        filter_condition = Q()
        for filter_field, val in request.GET.items():
            if filter_field != "page":
                filter_condition.children.append((filter_field, val))
        return filter_condition

    # 显示页面数据
    def list_view(self, request):
        if request.method == "POST":  # action方法
            action = request.POST.get("action")
            selected_pk = request.POST.getlist("selected_pk")
            action_func = getattr(self, action)  # self当前类的actions = [patch_init]
            queryset = self.model.objects.filter(pk__in=selected_pk)
            ret = action_func(request, queryset)

        # 获取serach的Q对象
        search_connection = self.get_serach_condtion(request)

        # 获取filter构建Q对象
        filter_condition = self.get_filter_condition(request)

        # 筛选获取当前表所有数据
        data_list = self.model.objects.all().filter(search_connection).filter(filter_condition)

        # 按这ShowList展示页面
        showlist = ShowList(self, data_list, request)

        # 构建一个查看URL
        add_url = self.get_add_url()
        # locals()函数会以dict类型返回当前位置的全部局部变量
        return render(request, "list_view.html", locals())

    def extra_url(self):
        # 新增url，有就添加没有就是空
        return []

    # 匹配增删改查的四种url模式
    def get_urls_2(self):
        temp = []
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label
        # 设计url别名,避免修改匹配的url路径后的大量修改
        temp.append(url(r"^add/", self.add_view, name="%s_%s_add" % (app_label, model_name)))
        temp.append(url(r"^(\d+)/delete/", self.delete_view, name="%s_%s_delete" % (app_label, model_name)))
        temp.append(url(r"^(\d+)/change/", self.change_view, name="%s_%s_change" % (app_label, model_name)))
        temp.append(url(r"^$", self.list_view, name="%s_%s_list" % (app_label, model_name)))
        temp.extend(self.extra_url())
        return temp

    @property
    def urls_2(self):  # 2级分发urls生成不同样式类的多个实例
        return self.get_urls_2(), None, None


# 2.注册
class StarkSite(object):
    def __init__(self):
        self._registry = {}

    # 判断用户传没传数据表和关联字段
    def register(self, model, stark_class=None):
        if not stark_class:  # 不传关联字段
            stark_class = ModelStark  # 采用默认样式
        self._registry[model] = stark_class(model, self)  # 传了就保存进_registry字典
        # 数据表                # 表的实例对象

    # 存储用户访问的当前app和数据表为列表
    def get_urls(self):
        temp = []
        for model, stark_class_obj in self._registry.items():
            model_name = model._meta.model_name  # 获取当前数据表名
            app_label = model._meta.app_label  # 获取当前app名
            # 字符串拼接当前 app+model 的url前缀                     为保证不同数据表不同样式开辟2级分发urls_2
            temp.append(url(r"^%s/%s/" % (app_label, model_name), stark_class_obj.urls_2))
        return temp

    @property  # property把类方法变为属性调用
    def urls(self):  # 1级分发urls
        return self.get_urls(), None, None


site = StarkSite()  # ModelStark类对StarkSite类的单列调用为实例













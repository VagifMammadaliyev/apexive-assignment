from django.db import models
from django.conf import settings
from django.utils import timezone, translation

from ontime.utils import smart_slugify
from content.utils import slugify_translated_fields
from ckeditor.fields import RichTextField
from ckeditor_uploader.fields import RichTextUploadingField


def get_announcement_image(instance, filename):
    return "content/announcements/%s/%s/%s" % (
        smart_slugify(instance.slug),
        timezone.now().strftime("%Y/%m/%d"),
        filename,
    )


class Announcement(models.Model):
    """Model for News. Just named it more formally"""

    slug = models.SlugField(max_length=100, unique=True, allow_unicode=True)
    title = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to=get_announcement_image)
    preview = models.TextField(null=True, blank=True)
    body = RichTextUploadingField(null=True, blank=True)
    pinned = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "announcement"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        slugify_translated_fields(self, "title")
        return super().save(*args, **kwargs)


class FAQCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, allow_unicode=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = "faq_category"
        verbose_name = "FAQ Category"
        verbose_name_plural = "FAQ Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        slugify_translated_fields(self, "name")
        return super().save(*args, **kwargs)


class FAQ(models.Model):
    category = models.ForeignKey(
        "content.FAQCategory", on_delete=models.SET_NULL, null=True, blank=True
    )
    question = models.CharField(max_length=150)
    answer = RichTextUploadingField()
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = "faq"
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


def get_service_image(instance, filename):
    return "content/services/%s_%s" % (instance.title, filename)


class Service(models.Model):
    title = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = RichTextUploadingField()
    preview = models.TextField()

    image = models.ImageField(upload_to=get_service_image)

    class Meta:
        db_table = "our_service"

    def __str__(self):
        return "Service [%s]" % self.title

    def save(self, *args, **kwargs):
        slugify_translated_fields(self, "title")
        return super().save(*args, **kwargs)


def get_slider_image(instance, filename):
    return "content/sliders/%s_%s" % (instance.title, filename)


class SliderItem(models.Model):
    title = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    background_image = models.ImageField(upload_to=get_slider_image)
    link = models.URLField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "slider_item"

    def __str__(self):
        return "Slider [%s]" % (self.title)


class FlatPage(models.Model):
    CONDITIONS_TYPE = "ct"
    SIMPLE_TYPE = "st"
    OFFER_TYPE = "ot"
    TYPES = (
        (CONDITIONS_TYPE, "Terms and conditions"),
        (SIMPLE_TYPE, "Simple flat page"),
        (OFFER_TYPE, "Offer text"),
    )

    type = models.CharField(choices=TYPES, max_length=2, default=SIMPLE_TYPE)

    title = models.CharField(max_length=500, unique=True)
    slug = models.SlugField(unique=True, max_length=255)
    body = RichTextUploadingField(null=True, blank=True)
    preview = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "flat_page"

    def __str__(self):
        return "Flat page [%s]" % (self.title)

    def save(self, *args, **kwargs):
        slugify_translated_fields(self, "title")
        return super().save(*args, **kwargs)


class FooterColumn(models.Model):
    title = models.CharField(max_length=100)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "footer_column"

    def __str__(self):
        return "Footer column [%s]" % self.title


class FooterElement(models.Model):
    column = models.ForeignKey(
        "content.FooterColumn",
        on_delete=models.CASCADE,
        related_name="elements",
        related_query_name="element",
    )
    title = models.CharField(max_length=100)
    raw_link = models.URLField(blank=True, null=True)
    flat_page = models.ForeignKey(
        "content.FlatPage",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "footer_element"

    def __str__(self):
        return "Footer element [%s]" % (self.title)


class SitePreset(models.Model):
    title = models.CharField(max_length=100)
    about_text_title = models.CharField(max_length=255, null=True, blank=True)
    about_text_preview = models.TextField(null=True, blank=True)
    about_text = RichTextUploadingField(null=True, blank=True)
    main_office_address = models.TextField(null=True, blank=True)
    emails = models.TextField(
        help_text='Example: "support@ontime.az, help@ontime.az" without quotes',
        null=True,
        blank=True,
    )
    phone_numbers = models.TextField(
        help_text='Example: "+9945555555, +994515555555" without quotes',
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "site_preset"

    def __str__(self):
        return "Site preset [%s]" % (self.title)

    def save(self, *args, **kwargs):
        # Deactivate other presets
        if not self.pk and self.is_active:
            SitePreset.objects.all().update(is_active=False)
        elif self.pk and self.is_active:
            SitePreset.objects.exclude(pk=self.pk).update(is_active=True)
        return super().save(*args, **kwargs)

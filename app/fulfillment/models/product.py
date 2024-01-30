from django.db import models
from django.conf import settings

from fulfillment.models.abc import SoftDeletionModel


class ParentProductCategory(models.Model):
    """
    Model used for statistical purposes. At least for now.
    """

    name = models.CharField(max_length=200)

    class Meta:
        db_table = "parent_product_category"
        verbose_name_plural = "Parent Product Categories"

    def __str__(self):
        return self.name


class ProductCategory(models.Model):
    parent = models.ForeignKey(
        "fulfillment.ParentProductCategory",
        related_name="children",
        related_query_name="child",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    name = models.CharField(max_length=200)
    hs_code = models.CharField(max_length=50, blank=True, null=True)
    needs_description = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    customs_product_type = models.ForeignKey(
        "fulfillment.CustomsProductType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "product_category"
        verbose_name_plural = "Product categories"

    def __str__(self):
        return self.name


class ProductType(models.Model):
    name = models.CharField(max_length=50)
    category = models.ForeignKey(
        "fulfillment.ProductCategory",
        on_delete=models.CASCADE,
        related_name="product_types",
        related_query_name="product_type",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "product_type"

    def __str__(self):
        return "%s [%s]" % (self.name, self.category)


class Product(SoftDeletionModel):
    package = models.ForeignKey(
        "fulfillment.Package",
        on_delete=models.CASCADE,
        related_name="products",
        related_query_name="product",
    )
    category = models.ForeignKey(
        "fulfillment.ProductCategory",
        on_delete=models.PROTECT,
        related_name="products",
        related_query_name="product",
    )
    type = models.ForeignKey(
        "fulfillment.ProductType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        related_query_name="products",
    )
    description = models.CharField(max_length=400, null=True, blank=True)
    url = models.URLField(max_length=3000, null=True, blank=True)

    price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    cargo_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    commission_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    cargo_price_currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    commission_price_currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1)
    order = models.ForeignKey(
        "fulfillment.Order",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )

    warehouseman_description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "product"

    def __str__(self):
        return self.normalized_description

    @property
    def normalized_description(self):
        chunks = []
        if self.type and self.type.category:
            chunks.append(self.type.category.name_en)
        elif self.category:
            chunks.append(self.category.name_en)
        else:
            return self.description
        if self.type:
            chunks.append(self.type.name_en)
        else:
            if self.description:
                return self.description
        return " / ".join(chunks)


class ProductPhoto(models.Model):
    product = models.ForeignKey(
        "fulfillment.Product",
        related_name="photos",
        related_query_name="photo",
        on_delete=models.CASCADE,
    )
    file = models.ImageField(upload_to="products/photos/%Y/%m/%d")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_photo"

    def __str__(self):
        return f"Photo of [{self.product}]"


class OrderedProduct(models.Model):
    # User, Order, Shipment are just for logging purposes
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    order = models.ForeignKey(
        "fulfillment.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    shipment = models.ForeignKey(
        "fulfillment.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    user_description = models.CharField(max_length=500, null=True, blank=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    url = models.URLField(max_length=1000)
    color = models.CharField(max_length=100, null=True, blank=True)
    size = models.CharField(max_length=100, null=True, blank=True)
    image = models.URLField(max_length=1000, null=True, blank=True)
    country = models.ForeignKey("core.Country", on_delete=models.CASCADE)
    category = models.ForeignKey(
        "fulfillment.ProductCategory",
        on_delete=models.PROTECT,
        related_name="ordered_products",
        related_query_name="ordered_product",
    )
    price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )

    # From shipment
    shipping_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    shipping_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    shop = models.ForeignKey(
        "fulfillment.Shop",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_query_name="ordered_product",
        related_name="ordered_products",
    )

    is_visible = models.BooleanField(default=False)

    class Meta:
        db_table = "ordered_product"

    def __str__(self):
        return self.description or self.user_description or "No description"


class CustomsProductType(models.Model):
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        related_query_name="child",
        on_delete=models.SET_NULL,
    )
    name = models.CharField(max_length=999)
    original_id = models.IntegerField(db_index=True, unique=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        parent_name = self.parent.name if self.parent else ""
        if parent_name:
            return f"{parent_name} - {self.name}"
        return self.name

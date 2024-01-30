"""
Strings used in application extracted here for better maintainability.
"""
from django.utils.translation import gettext_lazy as _

AT_LEAST_ONE_DIGIT_IN_PASSWORD = _("Şifrənizdə ən azı 1 rəqəm olmalıdır")
AT_LEAST_8_SYMBOLS_IN_PASSWORD = _("Şifrəniz ən azı 8 simvoldan ibarət olmalıdır")
ALREADY_USER_EMAIL = _("Bu E-poçt artıq istifadə olunur")
INVALID_ID_NUMBER = _("Yalnış seriya nömrəsi")
INVALID_ID_PIN = _("Yalnış FİN kod")
ACCOUNT_ACTIVATED = _("Hesabınız təsdiqləndi")
EMAIL_VERIFIED = _("E-poçtunuz təsdiqləndi")
SENT_VERIFICATION_SMS = _("Telefon nömrənizə təsdiqlənmə kodu göndərildi")
RESENT_VERIFICATION_SMS = _("Təsdiqlənmə kodu yenidən göndərildi")
REQUIRED_FIELD = _("Bu sahə vacibdir")
USER_ROLE = _("İstifadəçi")
ADMIN_ROLE = _("Admin")
CASHIER_ROLE = _("Kassir")
WAREHOUSEMAN_ROLE = _("Anbardar")
SHOPPING_ASSISTANT_ROLE = _("Alış-veriş köməkçisi")
CONTENT_MANAGER_ROLE = _("Kontent menecer")
CUSTOMER_SERVICE_ROLE = _("Müştəri xidməti")
MONITOR_ROLE = _("Monitor")
COURIER_ROLE = _("Kuryer")
CUSTOMS_AGENT_ROLE = _("Gömrük Agenti")
MALE_SEX = _("Kişi")
FEMALE_SEX = _("Qadın")
PAYMENT_SYSTEM_CONNECTION_ERROR = _("Ödəniş sisteminə bağlanmada xəta")
INVALID_OR_MALFORMED_DATA = _("Yalnış və ya qüsurlu məlumat")
INVALID_AMOUNT_FORMAT = _("Məbləğ düzgün formatda deyil")
AMOUNT_MUST_BE_BIGGER_THAN_ZERO = _("Məbləğ 0-dan böyük olmalıdır")
INVALID_CURRENCY = _("Yalnış valyuta")
CANT_CREATE_SHIPMENT_WITHOUT_PACKAGE = _("Bağlamasız göndərmə yaradıla bilməz")
CANT_SEND_TO_SELECETED_WAREHOUSE = _(
    "Seçilən anbara göndərilə bilməz, adres məlumatlarınızı yoxlayın"
)
INVALID_NEW_PAYMENT_TYPE = _("Yeni ödəniş növü yalnışdır")
ALREADY_PAID = _("Artıq ödənilib")
PAYMENT_TYPES_AND_CURRENCIES_MUST_BE_THE_SAME = _(
    "Üsullar və valyutalar eyni olmalıdırlar"
)
CARD_PAYMENT_FAILED = _("Kartla ödəniş uğursuz")
ORDER_PLACED_FMT = _("Sifarişiniz yerləşdirildi (%(order_code)s)")
SHIPMENT_PRICE_NOT_SET = _("Gönərmənin qiyməti təyin olunmayıb")
SHIPMENT_STATUS_UPDATED_FMT = _(
    "%(shipment_number)s nömrəli göndərmənin statusu yeniləndi"
)
SHIPMENT_IS_BEING_PREPARED_FOR_FLIGHT_FMT = _(
    "Göndərmə uçuş üçün hazırlanır (%(city)s)"
)
SHIPMENT_LEFT_FOREIGN_WAREHOUSE_FMT = _("Göndərmə xarici anbarı tərk etdi (%(city)s)")
SHIPMENT_ARRIVED_INTO_LOCAL_WAREHOUSE_FMT = _(
    "Göndərmə yerli anbara daxil oldu (%(warehouse)s)"
)
SHIPMENT_GIVEN_TO_CUSTOMER = _("Göndərmə təhvil verildi")
SHIPMENT_ON_CUSTOMS = _("Göndərmə gömrükdə")
PROBLEMATIC_PACKAGE = _("Problemli bağlama")
PROBLEMATIC_PACKAGE_MESSAGE_BODY_FMT = _(
    "Sizin adınıza %(tracking_code)s izləmə kodu ilə bağlama xarici anbara daxil olub. Xahiş edirik bağlama haqqında məlumatı tamamlayasız"
)
PACKAGES_ARRIVED_INTO_FOREIGN_WAREHOUSE_FMT = _(
    "Bağlamanız xarici anbara daxil oldu (%(tracking_code)s)"
)
PACKAGES_ARRIVED_INTO_FOREIGN_WAREHOUSE_MESSAGE_BODY_FMT = _(
    "Sizin %(tracking_code)s izləmə kodu ilə bağlama xarici anbarımıza daxil oldu"
)
NEW_AWAITING_PAYMENT_FMT = _("Yeni gözlənilən ödəniş (%(order_code)s)")
ORDER_WILL_BE_PROCESSED_AFTER_PAYMENT = _("Sifariş ödəndikdən sonra icra olunacaq")
SHIPMENT_PRICE_CANNOT_BE_SET = _(
    "Göndərmənin qiyməti təyin oluna bilməmişdır. Tarifləri yoxlayın"
)
SHIPMENT_PRICE_WAS_SET_FMT = _(
    "%(shipment_number)s nömrəli göndərmənizin qiyməti təyin olundu"
)
SHIPMENT_PRICE_WAS_SET_MESSAGE_BODY_FMT = _(
    "%(shipment_number)s nömrəli göndərmənizi ya online balansınız ilə və ya təhvil alan vaxtı ödəyə bilərsiz"
)
ORDER_IS_NOT_PAID = _("Sifariş ödənilməyib")
ORDER_CANNOT_BE_REJECTED = _("Sifariş ləğv oluna bilməz")
SHIPMENT_WAS_REJECTED_FMT = _("Sifarişiniz ləğv olundu (%(order_code)s)")
SHIPMENT_WAS_REJECTED_MESSAGE_BODY_FMT = _(
    "Sifarişiniz ləğv olundu və ödədiyiniz məbləğ (%(refund_amount)s) balansınıza geri qaytarıldı"
)
ORDER_DOES_NOT_HAVE_REMAINDER_PRICE = _(
    "Sifarişin artıq yada əskiy ödəniş məbləği yoxdur"
)
PAYMENT_WAS_UPDATED_FMT = _("Ödənişiniz yeniləndi (%(order_code)s)")
PAYMENT_WAS_UPDATED_MESSAGE_BODY_FMT = _(
    "%(order_code)s nömrəli sifariş üçün ödəniş məbləği operator tərəfindən səhv qeyd edildiyinə görə yeniləndi"
)
MISTAKE_IN_ORDER_PRICE_VALUES_FMT = _(
    "Sifarişinizin qiymətində yalnışlıq (%(order_code)s)"
)
MISTAKE_IN_ORDER_PRICE_VALUES_MESSAGE_BODY_FMT = _(
    "%(order_code)s nömrəli sifariş üçün qeyd etdiyiniz qiymət yalnış olduğuna görə qalıq məbləği ödəməniz xahış olunur"
)
REFUNDED_REMAINDER_PRICE_FMT = _("Artıq ödənişinizi sizə qaytardıq (%(order_code)s)")
REFUNDED_REMAINDER_PRICE_MESSSAGE_BODY_FMT = _(
    "%(order_code)s nömrəli sifarişdə qeyd etdiyiniz qiymət artıq olduğuna görə balansınıza qaytardıq"
)
BOX_DEST_WAREHOUSE_CANNOT_BE_DEFINED = _(
    "Boks üçün çatdırılacaq anbar müəyyənləşə bilmədi"
)
AT_LEAST_ONE_SHIPMENT_IS_NOT_CONFIRMED = _("Göndərmələrin ən azı biri təsdiqlənməyib")
THIS_BOX_IS_ALREADY_SENT = _("Bu boks artıq göndərilib və ya göndərilmə üzrədir")
SHIPMENT_ALREADY_CONFIRMED_OR_CANNOT_BE_CONFIRMED = _(
    "Göndərmə artıq təsdiqlənib və ya təsdiqlənə bilməz. Ölçülərin, çəkisini, servis olunduğunu və ya tarifləri yoxlayın"
)
SOME_SERVICES_DOES_NOT_HAVE_REQUESTED_ATTACHMENTS = _(
    "Qoşma tələb edən bəzi servislərin qoşmaları yoxdur"
)
YOUR_SHIPMENT_IS_ON_CUSTOMS_NOW_FMT = _(
    "Sizin %(shipment_number)s nömrəli göndərməniz hal hazırda gömrükdədir"
)
YOUR_SHIPMENT_IS_ON_CUSTOMS_NOW_MESSAGE_BODY_FMT = _(
    "Sizin %(shipment_number)s nörməli göndərməniz gömrükdədir. Status: %(tracking_status)s"
)
TARIFF_PRICE = _("Tarif qiyməti")
SERVICE_DESCRIPTION_FMT = _("Servis: %(service_title)s")
PACKAGE_SERVICE_DESCRIPTION_FMT = _(
    "Bağlama %(package_tracking_code)s servisi: %(service_title)s"
)
PRODUCT_PRICE = _("Malın qiyməti")
INCOUNTRY_CARGO_PRICE = _("Ölkədaxili karqo")
COMMISSION_PRICE = _("Kommissiya haqqı")
SHIPMENTS_ARE_ALREADY_DONE_OR_IN_QUEUE = _(
    "Göndərmələr ya artıq təhvil verilib, yada artıq növbədədirlər."
)
NO_QUEUED_ITEM = _("Növbədə gözləyən yoxdur")
QUEUE_IS_ALREADY_SET = _("Növbə artıq təyin olunub")
CANT_SET_TO_CUSTOMER_SERVICE_QUEUE = _("Müştəri xidməti növbəsinə təyin oluna bilməz")
CANT_RESET_WAREHOUSEMAN_QUEUE = _("Anbardar növbəsinə təkrar təyin oluna bilməz")
CANT_RESET_CASHIER_QUEUE = _("Kassir növbəsinə təkrar təyin oluna bilməz")
CANT_SET_TO_CASHIER_QUEUE_BYPASSING_WAREHOUSEMAN_APPROVAL = _(
    "Anbardar hazır etməmiş kassir növbəsinə təyin oluna bilməz"
)
CANT_SET_TO_CASHIER_QUEUE = _("Kassir növbəsinə təyin oluna bilməz")
CAN_SET_ONLY_TO_CUSTOMER_SERVICE_QUEUE = _(
    "Yalnız müştəri xidməti növbəsinə təyin oluna bilər"
)
NUMBER_ALREADY_IN_USE = _("Bu nömrə arıq istifadə olunur")
FULL_PHONE_NUMBER_MUST_BE_PROVIDED = _("Tam telefon nömrəniz qeyd olunmalıdır.")
UNSUPPORTED_PHONE_NUMBER = _("Qeyd etdiyiniz telefon nömrəsi dəstəklənmir")
ERROR_OCCURRED = _("Xəta baş verdi")
PROFILE_ERROR_OCCURRED = _("Profil xətası baş verdi")
PROFILE_INCOMPLETE_ERROR = _("Profiliniz tamamlanmayıb")
INVALID_CONFIRMATION_CODE_ERROR = _("Təsdiqlənmə kodu yalnışdır")
ALREADY_CONFIRMED_ERROR = _("Artıq təsdiqlənib")
EMAIL_CANNOT_BE_VERIFIED_ERROR = _("E-poçtunuz təsdiqlənmədi")
BALANCE_OPERATION_ERROR = _("Balans əməliyyat xətası")
BALANCE_HAS_INSUFFICIENT_AMOUNT_ERROR = _("Balansda kifayət qədər məbləğ yoxdur")
USER_DATA_INCOMPLETE_ERROR = _("İstifadəçi məlumatları tam deyil")
ORDER_RELATED_ERROR = _("Sifarişlə bağlı xəta baş verdi")
THIS_OPERATION_CANNOT_BE_DONE_ERROR = _("Bu əməliyyat baş verə bilməz")
PACKAGES_MUST_HAVE_SAME_SOURCE_COUNTRY_ERROR = _("Bağlamalar bir ölkəyə aid olmalıdır")
ONE_OF_THE_PACKAGES_IS_ALREADY_ACCEPTED_ERROR = _(
    "Bağlamalardan birin artıq qəbul etmisiz"
)
BOX_IS_INVALID_ERROR = "Boks yalnışdır"
QUEUE_ERROR = _("Növbə xətası")
NO_QUEUE_IN_WAREHOUSE_ERROR = _("Anbarda növbə mövcud deyil")
PAYMENT_DID_NOT_SUCCESS_ERROR = _("Ödəniş baş vermədi")
SYSTEM_MESSAGE = _("Sistem mesajı")
FOR_PAYMENT = _("Ödəniş üçün")
FOR_ORDER = _("Sifariş üçün")
FOR_SHIPMENT = _("Göndərmə üçün")
FOR_PACKAGE = _("Bağlama üçün")
OTHER = _("Başqa")
TO_CASHIER = _("Kassir növbəsi")
TO_WAREHOUSEMAN = _("Anbardar növbəsi")
TO_CUSTOMER_SERVICE = _("Müştəri xidməti növbəsi")
FOR_QUEUE = _("Növbə üçün")
FOR_CUSTOMER = _("Müştəri üçün")
PACKAGE_TYPE = _("Bağlamalar üçün")
SHIPMENT_TYPE = _("Göndərmələr üçün")
BY_AIR = _("Hava ilə")
ORDER_TYPE = _("Sifarişlər üçün")
PACKAGE_TYPE = _("Bağlamalar üçün")
SHIPMENT_TYPE = _("Göndərmələr üçün")
COURIER_ORDER_TYPE = _("Kuryer sifarişləri üçün")
ORDER_TYPE = _("Sifarişlər üçün")
PACKAGE_TYPE = _("Bağlamalar üçün")
SHIPMENT_TYPE = _("Göndərmələr üçün")
COURIER_ORDER_TYPE = _("Kuryer sifarişləri üçün")
TICKET_TYPE = _("Müraciətlər üçün")
ORDER_PAYMENT = _("Sifariş ödənişi")
SHIPMENT_PAYMENT = _("Göndərmə ödənişi")
ORDER_REMAINDER_PAYMENT = _("Sifariş qalığı ödənişi")
ORDER_REFUND = _("Sifarişin geri ödənişi")
ORDER_REMAINDER_REFUND = _("Sifarişin artıq ödənişin qaytarılması")
SHIPMENT_REFUND = _("Göndərmənın geri ödənişi")
BALANCE_INCREASE = _("Balans artırılması")
BALANCE_DECREASE = _("Balansdan çıxarış")
MERGED = _("Birləşmiş")
CARD = _("Kart")
CASH = _("Nağd")
BALANCE = _("Balans")
MUST_BE_GIVEN_WITH_DEST_CITY = _("Təyinat şəhəri ilə birlikdə verilməlidir")
MUST_BE_GIVEN_WITH_SOURCE_CITY = _("Mənbə şəhəri ilə birlikdə verilməlidir")
MUST_BE_GIVEN_WITH_DEST_COUNTRY = _("Təyinat ölkəsi ilə birlikdə verilməlidir")
MUST_BE_GIVEN_WITH_SOURCE_COUNTRY = _("Mənbə ölkəsi ilə birlikdə verilməlidir")
MISSING_PRODUCT_TYPE = _("Məhsulun kateqoriyasına uyğun növ seçilməlidir")
MISSING_RECIPIENT = _("Birbaşa göndərmək üçün alıcı mütləqdir")
MISSING_DESTINATION_WAREHOUSE = _("Birbaşa göndərmək üçün təyinan anbar mütləqdir")
INVALID_PRODUCT_TYPE = _("Məhsul növu yalnışdır")
CUSTOMS_DESCRIPTION = _("Gomrük üçün malın haqqında məlumat mütləqdir")
BAD_ADDRESS = _("Adres sizə məxsus deyil")
ONE_CLICK_ADDRESS_REQURIED = _("Gözləmədən göndərilərsə adres mütləqdir")
INVALID_FORMAT = _("Yalnış format")
NO_CONSOLIDATION_FOR_THIS_COUNTRY = _("Bu ölkə üçün göndərmə sonradan formalaşa bilməz")
NOT_SERVICED_PACKAGE_CANNOT_BE_SENT_FMT = _(
    "%(tracking_code)s göndərilə bilməz. Servis olunmayıb"
)
PACKAGE_NOT_FOUND_FMT = _("%(tracking_codes)s bağlamalarınızda tapılmadı")
INVALID_WAREHOUSE_FOR_SELECTED_COUNTRY = _("Anbar seçilən ölkəyə uyğun deyil")
REAL_CUSTOMER_WARNING = _("Malın əsl yiyəsi deyilsə bu xana boş olmamalıdır")
CANT_SEND_TO_YOUR_WAREHOUSE = _("Sizin olduğunuz anbara göndərilə bilməz")
NEW_COMMENT_FOR_ORDER_FMT = _("%(order_code)s üçün yeni rəy")
NEW_COMMENT_FOR_ORDER_MESSAGE_BODY_FMT = _("Mətn: %(comment)s")
DATA_IS_EMPTY_OR_INVALID = _("Məlumatlar yalnış və ya boşdur.")
PAYMENT_NOT_FOUND = _("Ödəniş tapılmadı")
PAYPAL_PAYMENT_ERROR = _("PayPal ilə ödənişdə xəta")
SMS_CANNOT_BE_SENT = _("Mesaj göndərilə bilmədi")
SMS_INVALID_OR_OUT_OF_SERVICE_RECIPIENT_NUMBER = _(
    "Müştərinin telefon nömrəsi yalnış və ya xidmət əhatəsindən xaric"
)
ID_INVALID_FOR_PROVIDED_TYPE = _("Göstərilən növ üçün obyekt tapılmadı")
ALREADY_HAS_TICKET = _("Artıq müraciət var")
ORDER_WORD = _("Sifariş")
PACKAGE_WORD = _("Bağlama")
SHIPMENT_WORD = _("Çatdırılma")
PAYMENT_WORD = _("Ödəniş")
RECIPIENT_DOES_NOT_BELONGS_TO_USER = _("Alıcı məlumatı istifadəçiyə aid deyil")
SHIPMENTS_DOES_NOT_BELONGS_TO_USER_FMT = _(
    "Çatdırmalar istifadəçiyə aid deyil: %(numbers)s"
)
COURIER_ORDER_PAYMENT = _("Kuryer ödənişi")
COURIER_ORDER_PAYMENT_TITLE_FMT = _("Kuryer ödənişi: %(count)s çatdırma")
USER_ALREADY_HAS_ENOUGH_BALANCE = _("Artıq lazımi qədər məbləğ balansınızdadır")
ONLY_BALANCE_PAYMENTS_CAN_BE_PARTIONATED = _("Ancaq balansla ödənişləri bölmək olar")
INVALID_PASSWORD = _("Yalnış parol")
INVALID_RESET_CODE = _("Yalnış kod")
COURIER_PRICE = _("Kuryer ödənişi")
MIN_TARIFF_FMT = _("%(price)s%(currency)s-dan")
DISABLED_COUNTRY_ERROR = _("Bu ölkə üçün göstərilən əməliyyat aparıla bilməz")
INVALID_TARIFF_FOR_SELECTED_REGION = _("Seçdiyiniz region üçün tarif yanlışdır")
ONE_IS_REQUIRED = _("Biri mütləqdir")
LOGIN_FAILED = _("Yalnış hesab məlumatları")
INVITE_FRIEND_DISCOUNT_REASON = _("Promo kod endirimi")
SIMPLE_DISCOUNT_REASON = _("Endirim")
INVITE_FRIEND_INVALID_PROMO_CODE = _("Yanlış promo kod")
CASHBACK = _("Cashback")
ULDUZUM_IDENTICAL_CODE_INVALID = _("Promo kod yanlış")
WRONG_ACCEPTING_WAREHOUSE_ERROR = _("Bağlama bu anbara gelmeyib")
ALREADY_ARCHIVED = _("Artıq arxivləşdirilib")
CANNOT_ARCHIVED = _("Arxivəşdirilə bilməz")
TERMINAL = _("Terminal")

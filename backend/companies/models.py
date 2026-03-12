# backend/companies/models.py

import uuid
from django.conf import settings
from django.db import models


class IndustryChoices(models.TextChoices):
    MANUFACTURING = 'MANUFACTURING', 'Manufacturing'
    TRADING = 'TRADING', 'Trading / Wholesale / Retail'
    SERVICES = 'SERVICES', 'Services / Consulting'
    CONSTRUCTION = 'CONSTRUCTION', 'Construction / Real Estate'
    HEALTHCARE = 'HEALTHCARE', 'Healthcare / Pharmaceuticals'
    IT_SOFTWARE = 'IT_SOFTWARE', 'IT / Software / Technology'
    AGRICULTURE = 'AGRICULTURE', 'Agriculture / Farming'
    EDUCATION = 'EDUCATION', 'Education'
    HOSPITALITY = 'HOSPITALITY', 'Hospitality / Food & Beverage'
    TRANSPORTATION = 'TRANSPORTATION', 'Transportation / Logistics'
    OTHER = 'OTHER', 'Other'


class CompanySizeChoices(models.TextChoices):
    MICRO = '1-10', '1–10 Employees'
    SMALL = '11-50', '11–50 Employees'
    MEDIUM = '51-200', '51–200 Employees'
    LARGE = '200+', '200+ Employees'


class InventoryMethodChoices(models.TextChoices):
    FIFO = 'FIFO', 'First In, First Out (FIFO)'
    WEIGHTED_AVERAGE = 'WEIGHTED_AVERAGE', 'Weighted Average'


class DateFormatChoices(models.TextChoices):
    DD_MM_YYYY = 'DD/MM/YYYY', 'DD/MM/YYYY'
    MM_DD_YYYY = 'MM/DD/YYYY', 'MM/DD/YYYY'
    YYYY_MM_DD = 'YYYY-MM-DD', 'YYYY-MM-DD'


class SubscriptionPlanChoices(models.TextChoices):
    FREE_TRIAL = 'FREE_TRIAL', 'Free Trial'
    BASIC = 'BASIC', 'Basic'
    PRO = 'PRO', 'Professional'
    ENTERPRISE = 'ENTERPRISE', 'Enterprise'


class CurrencyChoices(models.TextChoices):
    AED = 'AED', 'AED — UAE Dirham'
    AFN = 'AFN', 'AFN — Afghan Afghani'
    ALL = 'ALL', 'ALL — Albanian Lek'
    AMD = 'AMD', 'AMD — Armenian Dram'
    ANG = 'ANG', 'ANG — Netherlands Antillean Guilder'
    AOA = 'AOA', 'AOA — Angolan Kwanza'
    ARS = 'ARS', 'ARS — Argentine Peso'
    AUD = 'AUD', 'AUD — Australian Dollar'
    AWG = 'AWG', 'AWG — Aruban Florin'
    AZN = 'AZN', 'AZN — Azerbaijani Manat'
    BAM = 'BAM', 'BAM — Bosnia Convertible Mark'
    BBD = 'BBD', 'BBD — Barbadian Dollar'
    BDT = 'BDT', 'BDT — Bangladeshi Taka'
    BGN = 'BGN', 'BGN — Bulgarian Lev'
    BHD = 'BHD', 'BHD — Bahraini Dinar'
    BIF = 'BIF', 'BIF — Burundian Franc'
    BMD = 'BMD', 'BMD — Bermudian Dollar'
    BND = 'BND', 'BND — Brunei Dollar'
    BOB = 'BOB', 'BOB — Bolivian Boliviano'
    BRL = 'BRL', 'BRL — Brazilian Real'
    BSD = 'BSD', 'BSD — Bahamian Dollar'
    BTN = 'BTN', 'BTN — Bhutanese Ngultrum'
    BWP = 'BWP', 'BWP — Botswana Pula'
    BYN = 'BYN', 'BYN — Belarusian Ruble'
    BZD = 'BZD', 'BZD — Belize Dollar'
    CAD = 'CAD', 'CAD — Canadian Dollar'
    CDF = 'CDF', 'CDF — Congolese Franc'
    CHF = 'CHF', 'CHF — Swiss Franc'
    CLP = 'CLP', 'CLP — Chilean Peso'
    CNY = 'CNY', 'CNY — Chinese Yuan'
    COP = 'COP', 'COP — Colombian Peso'
    CRC = 'CRC', 'CRC — Costa Rican Colón'
    CUP = 'CUP', 'CUP — Cuban Peso'
    CVE = 'CVE', 'CVE — Cape Verdean Escudo'
    CZK = 'CZK', 'CZK — Czech Koruna'
    DJF = 'DJF', 'DJF — Djiboutian Franc'
    DKK = 'DKK', 'DKK — Danish Krone'
    DOP = 'DOP', 'DOP — Dominican Peso'
    DZD = 'DZD', 'DZD — Algerian Dinar'
    EGP = 'EGP', 'EGP — Egyptian Pound'
    ERN = 'ERN', 'ERN — Eritrean Nakfa'
    ETB = 'ETB', 'ETB — Ethiopian Birr'
    EUR = 'EUR', 'EUR — Euro'
    FJD = 'FJD', 'FJD — Fijian Dollar'
    FKP = 'FKP', 'FKP — Falkland Islands Pound'
    GBP = 'GBP', 'GBP — British Pound Sterling'
    GEL = 'GEL', 'GEL — Georgian Lari'
    GHS = 'GHS', 'GHS — Ghanaian Cedi'
    GIP = 'GIP', 'GIP — Gibraltar Pound'
    GMD = 'GMD', 'GMD — Gambian Dalasi'
    GNF = 'GNF', 'GNF — Guinean Franc'
    GTQ = 'GTQ', 'GTQ — Guatemalan Quetzal'
    GYD = 'GYD', 'GYD — Guyanese Dollar'
    HKD = 'HKD', 'HKD — Hong Kong Dollar'
    HNL = 'HNL', 'HNL — Honduran Lempira'
    HTG = 'HTG', 'HTG — Haitian Gourde'
    HUF = 'HUF', 'HUF — Hungarian Forint'
    IDR = 'IDR', 'IDR — Indonesian Rupiah'
    ILS = 'ILS', 'ILS — Israeli New Shekel'
    INR = 'INR', 'INR — Indian Rupee'
    IQD = 'IQD', 'IQD — Iraqi Dinar'
    IRR = 'IRR', 'IRR — Iranian Rial'
    ISK = 'ISK', 'ISK — Icelandic Króna'
    JMD = 'JMD', 'JMD — Jamaican Dollar'
    JOD = 'JOD', 'JOD — Jordanian Dinar'
    JPY = 'JPY', 'JPY — Japanese Yen'
    KES = 'KES', 'KES — Kenyan Shilling'
    KGS = 'KGS', 'KGS — Kyrgyzstani Som'
    KHR = 'KHR', 'KHR — Cambodian Riel'
    KMF = 'KMF', 'KMF — Comorian Franc'
    KPW = 'KPW', 'KPW — North Korean Won'
    KRW = 'KRW', 'KRW — South Korean Won'
    KWD = 'KWD', 'KWD — Kuwaiti Dinar'
    KZT = 'KZT', 'KZT — Kazakhstani Tenge'
    LAK = 'LAK', 'LAK — Lao Kip'
    LBP = 'LBP', 'LBP — Lebanese Pound'
    LKR = 'LKR', 'LKR — Sri Lankan Rupee'
    LRD = 'LRD', 'LRD — Liberian Dollar'
    LSL = 'LSL', 'LSL — Lesotho Loti'
    LYD = 'LYD', 'LYD — Libyan Dinar'
    MAD = 'MAD', 'MAD — Moroccan Dirham'
    MDL = 'MDL', 'MDL — Moldovan Leu'
    MGA = 'MGA', 'MGA — Malagasy Ariary'
    MKD = 'MKD', 'MKD — Macedonian Denar'
    MMK = 'MMK', 'MMK — Myanmar Kyat'
    MNT = 'MNT', 'MNT — Mongolian Tugrik'
    MOP = 'MOP', 'MOP — Macanese Pataca'
    MRU = 'MRU', 'MRU — Mauritanian Ouguiya'
    MUR = 'MUR', 'MUR — Mauritian Rupee'
    MVR = 'MVR', 'MVR — Maldivian Rufiyaa'
    MWK = 'MWK', 'MWK — Malawian Kwacha'
    MXN = 'MXN', 'MXN — Mexican Peso'
    MYR = 'MYR', 'MYR — Malaysian Ringgit'
    MZN = 'MZN', 'MZN — Mozambican Metical'
    NAD = 'NAD', 'NAD — Namibian Dollar'
    NGN = 'NGN', 'NGN — Nigerian Naira'
    NIO = 'NIO', 'NIO — Nicaraguan Córdoba'
    NOK = 'NOK', 'NOK — Norwegian Krone'
    NPR = 'NPR', 'NPR — Nepalese Rupee'
    NZD = 'NZD', 'NZD — New Zealand Dollar'
    OMR = 'OMR', 'OMR — Omani Rial'
    PAB = 'PAB', 'PAB — Panamanian Balboa'
    PEN = 'PEN', 'PEN — Peruvian Sol'
    PGK = 'PGK', 'PGK — Papua New Guinean Kina'
    PHP = 'PHP', 'PHP — Philippine Peso'
    PKR = 'PKR', 'PKR — Pakistani Rupee'
    PLN = 'PLN', 'PLN — Polish Zloty'
    PYG = 'PYG', 'PYG — Paraguayan Guarani'
    QAR = 'QAR', 'QAR — Qatari Riyal'
    RON = 'RON', 'RON — Romanian Leu'
    RSD = 'RSD', 'RSD — Serbian Dinar'
    RUB = 'RUB', 'RUB — Russian Ruble'
    RWF = 'RWF', 'RWF — Rwandan Franc'
    SAR = 'SAR', 'SAR — Saudi Riyal'
    SBD = 'SBD', 'SBD — Solomon Islands Dollar'
    SCR = 'SCR', 'SCR — Seychellois Rupee'
    SDG = 'SDG', 'SDG — Sudanese Pound'
    SEK = 'SEK', 'SEK — Swedish Krona'
    SGD = 'SGD', 'SGD — Singapore Dollar'
    SHP = 'SHP', 'SHP — Saint Helena Pound'
    SLE = 'SLE', 'SLE — Sierra Leonean Leone'
    SOS = 'SOS', 'SOS — Somali Shilling'
    SRD = 'SRD', 'SRD — Surinamese Dollar'
    SSP = 'SSP', 'SSP — South Sudanese Pound'
    STN = 'STN', 'STN — São Tomé and Príncipe Dobra'
    SYP = 'SYP', 'SYP — Syrian Pound'
    SZL = 'SZL', 'SZL — Eswatini Lilangeni'
    THB = 'THB', 'THB — Thai Baht'
    TJS = 'TJS', 'TJS — Tajikistani Somoni'
    TMT = 'TMT', 'TMT — Turkmenistani Manat'
    TND = 'TND', 'TND — Tunisian Dinar'
    TOP = 'TOP', 'TOP — Tongan Paʻanga'
    TRY = 'TRY', 'TRY — Turkish Lira'
    TTD = 'TTD', 'TTD — Trinidad and Tobago Dollar'
    TWD = 'TWD', 'TWD — New Taiwan Dollar'
    TZS = 'TZS', 'TZS — Tanzanian Shilling'
    UAH = 'UAH', 'UAH — Ukrainian Hryvnia'
    UGX = 'UGX', 'UGX — Ugandan Shilling'
    USD = 'USD', 'USD — United States Dollar'
    UYU = 'UYU', 'UYU — Uruguayan Peso'
    UZS = 'UZS', 'UZS — Uzbekistani Som'
    VES = 'VES', 'VES — Venezuelan Bolívar'
    VND = 'VND', 'VND — Vietnamese Dong'
    VUV = 'VUV', 'VUV — Vanuatu Vatu'
    WST = 'WST', 'WST — Samoan Tala'
    XAF = 'XAF', 'XAF — Central African CFA Franc'
    XCD = 'XCD', 'XCD — East Caribbean Dollar'
    XOF = 'XOF', 'XOF — West African CFA Franc'
    XPF = 'XPF', 'XPF — CFP Franc'
    YER = 'YER', 'YER — Yemeni Rial'
    ZAR = 'ZAR', 'ZAR — South African Rand'
    ZMW = 'ZMW', 'ZMW — Zambian Kwacha'
    ZWL = 'ZWL', 'ZWL — Zimbabwean Dollar'


class RoleChoices(models.TextChoices):
    OWNER = 'OWNER', 'Owner'
    ADMIN = 'ADMIN', 'Admin'
    ACCOUNTANT = 'ACCOUNTANT', 'Accountant'
    AUDITOR = 'AUDITOR', 'Auditor'
    SALES = 'SALES', 'Sales'
    INVENTORY = 'INVENTORY', 'Inventory'


class TaxCalculationTypeChoices(models.TextChoices):
    """
    How a tax layer calculates its amount.

    INDEPENDENT: Calculates on the original pre-tax amount.
    COMPOUND:    Calculates on (original amount + all previous layers).

    Example with 5% SD (independent) + 15% VAT (compound) on 10,000:
        SD  = 10,000 × 5%          = 500
        VAT = (10,000 + 500) × 15% = 1,575
        Total tax: 2,075 (effective rate: 20.75%)
    """
    INDEPENDENT = 'INDEPENDENT', 'Independent (on original amount)'
    COMPOUND    = 'COMPOUND', 'Compound (on amount + previous layers)'


class Company(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='company ID',
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_companies',
        verbose_name='owner',
    )

    name = models.CharField(
        max_length=200,
        verbose_name='company name',
    )

    trade_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='trade name',
    )

    industry = models.CharField(
        max_length=50,
        choices=IndustryChoices.choices,
        verbose_name='industry',
    )

    tax_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='BIN / Tax ID',
    )

    base_currency = models.CharField(
        max_length=3,
        choices=CurrencyChoices.choices,
        default=CurrencyChoices.BDT,
        verbose_name='base currency',
        help_text='Cannot be changed after first transaction is recorded.',
    )

    company_size = models.CharField(
        max_length=20,
        choices=CompanySizeChoices.choices,
        verbose_name='company size',
    )

    fiscal_year_start_month = models.IntegerField(
        choices=[(i, i) for i in range(1, 13)],
        default=7,
        verbose_name='fiscal year start month',
        help_text='Month number (1=January, 7=July, etc.)',
    )

    inventory_valuation_method = models.CharField(
        max_length=20,
        choices=InventoryMethodChoices.choices,
        default=InventoryMethodChoices.FIFO,
        verbose_name='inventory valuation method',
    )

    date_format = models.CharField(
        max_length=20,
        choices=DateFormatChoices.choices,
        default=DateFormatChoices.DD_MM_YYYY,
        verbose_name='date format',
    )

    is_vds_withholding_entity = models.BooleanField(
        default=False,
        verbose_name='VDS/withholding entity',
        help_text='Whether this company deducts VAT at source.',
    )

    lock_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='lock date',
        help_text='Transactions before this date are frozen. Only Owner/Admin can change.',
    )

    reporting_method = models.CharField(
        max_length=10,
        choices=[
            ('ACCRUAL', 'Accrual'),
            ('CASH', 'Cash'),
            ('BOTH', 'Both'),
        ],
        default='ACCRUAL',
        verbose_name='reporting method',
        help_text='Affects how financial reports calculate revenue/expense recognition.',
    )

    address = models.TextField(
        blank=True,
        null=True,
        verbose_name='street address',
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='city',
    )

    postal_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='postal code',
    )

    country = models.CharField(
        max_length=100,
        default='Bangladesh',
        verbose_name='country',
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='company phone',
    )

    website = models.URLField(
        blank=True,
        null=True,
        verbose_name='website',
    )

    time_zone = models.CharField(
        max_length=50,
        default='Asia/Dhaka',
        verbose_name='time zone',
    )

    subscription_plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlanChoices.choices,
        default=SubscriptionPlanChoices.FREE_TRIAL,
        verbose_name='subscription plan',
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='active',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='created at',
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='updated at',
    )

    class Meta:
        verbose_name = 'company'
        verbose_name_plural = 'companies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name'], name='idx_company_name'),
            models.Index(fields=['owner'], name='idx_company_owner'),
            models.Index(fields=['is_active'], name='idx_company_active'),
        ]

    def __str__(self):
        return self.name

    def has_financial_records(self):
        """
        Check if this company has any ledger entries recorded.
        Used to determine if base_currency can still be changed.
        """
        # Import here to avoid circular import at module level
        from journals.models import LedgerEntry
        return LedgerEntry.objects.filter(company=self).exists()



class   CompanyUser(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='membership ID',
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company_memberships',
        verbose_name='user',
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name='company',
    )

    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        verbose_name='role',
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='active membership',
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_invitations',
        verbose_name='invited by',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='joined at',
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='updated at',
    )

    class Meta:
        verbose_name = 'company member'
        verbose_name_plural = 'company members'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'company'],
                name='unique_user_company_membership',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'is_active'], name='idx_companyuser_user_active'),
            models.Index(fields=['company', 'is_active'], name='idx_companyuser_company_active'),
        ]

    def __str__(self):
        return f"{self.user.full_name} → {self.company.name} ({self.role})"



class PendingInvitation(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    email = models.EmailField(
        max_length=255,
        verbose_name='invited email',
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='pending_invitations',
        verbose_name='company',
    )

    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        verbose_name='assigned role',
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='pending_invitations_sent',
        verbose_name='invited by',
    )

    is_accepted = models.BooleanField(
        default=False,
        verbose_name='accepted',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='invited at',
    )

    class Meta:
        verbose_name = 'pending invitation'
        verbose_name_plural = 'pending invitations'
        ordering = ['-created_at']
        # One pending invitation per email per company
        constraints = [
            models.UniqueConstraint(
                fields=['email', 'company'],
                name='unique_pending_invitation_per_company',
            ),
        ]
        indexes = [
            models.Index(fields=['email', 'is_accepted'], name='idx_pending_email_accepted'),
        ]

    def __str__(self):
        return f"{self.email} → {self.company.name} ({self.role})"
    
class TaxProfile(models.Model):
    """
    A reusable tax configuration that can be applied to journal lines,
    invoice lines, bill lines, and any future transactional module.

    Examples:
        "VAT 15%"                     → Single layer, 15% independent
        "VAT 7.5%"                    → Single layer, 7.5% independent  
        "SD 5% + VAT 15% (Compound)"  → Two layers, SD independent + VAT compound

    When applied to a line, the system calculates the tax amount per layer
    and creates additional LedgerEntries for each tax account.

    The combined_rate field is pre-calculated for display purposes
    (showing "20.75%" in dropdowns). The actual calculation always
    uses the individual layer rates.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='tax_profiles',
    )

    name = models.CharField(
        max_length=100,
        verbose_name='tax profile name',
        help_text='e.g., "VAT 15%", "SD 5% + VAT 15%"',
    )

    combined_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        verbose_name='combined tax rate (%)',
        help_text='Total effective rate. Pre-calculated for display.',
    )


    is_active = models.BooleanField(
        default=True,
        verbose_name='active',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'tax profile'
        verbose_name_plural = 'tax profiles'
        ordering = ['name']

        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name'],
                name='unique_tax_profile_name_per_company',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.combined_rate}%)"


# ──────────────────────────────────────────────
# TAX PROFILE LAYER
# ──────────────────────────────────────────────

class TaxProfileLayer(models.Model):
    """
    A single tax layer within a TaxProfile.

    Each layer has its own rate, calculation type, and target ledger account.
    Layers are applied in order (apply_order = 1, 2, 3...).

    The default_tax_account is the ledger account where the calculated
    tax amount is posted. For example:
        - VAT layer → posts to "Output VAT Payable" (system account OUTPUT_VAT)
        - SD layer  → posts to "Supplementary Duty Payable"
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    tax_profile = models.ForeignKey(
        TaxProfile,
        on_delete=models.CASCADE,
        related_name='layers',
    )

    name = models.CharField(
        max_length=100,
        verbose_name='layer name',
        help_text='e.g., "VAT", "Supplementary Duty"',
    )

    rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        verbose_name='rate (%)',
        help_text='Tax percentage for this layer.',
    )

    calculation_type = models.CharField(
        max_length=15,
        choices=TaxCalculationTypeChoices.choices,
        default=TaxCalculationTypeChoices.INDEPENDENT,
        verbose_name='calculation type',
    )

    apply_order = models.PositiveIntegerField(
        verbose_name='application order',
        help_text='Execution order within the profile (1 = first).',
    )

    default_tax_account = models.ForeignKey(
        'chartofaccounts.Account',
        on_delete=models.PROTECT,
        related_name='tax_layer_defaults',
        verbose_name='default tax account',
        help_text='Ledger account where this tax layer posts.',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'tax profile layer'
        verbose_name_plural = 'tax profile layers'
        ordering = ['tax_profile', 'apply_order']

        constraints = [
            models.UniqueConstraint(
                fields=['tax_profile', 'apply_order'],
                name='unique_layer_order_per_profile',
            ),
        ]

    def __str__(self):
        return f"{self.tax_profile.name} → {self.name} ({self.rate}%)"


# ──────────────────────────────────────────────
# DOCUMENT SEQUENCE
# ──────────────────────────────────────────────

class DocumentSequence(models.Model):
    """
    Generates sequential document numbers for all modules.

    Each company + module combination gets its own counter.
    For example:
        Rahim Trading + MANUAL_JOURNAL → JE-0001, JE-0002, ...
        Rahim Trading + SALES_INVOICE  → INV-0001, INV-0002, ...
        Karim Industries + MANUAL_JOURNAL → JE-0001, JE-0002, ...

    CRITICAL — ATOMIC INCREMENT:
        The next_number field must be incremented using Django's F()
        expression or select_for_update() to prevent race conditions
        where two concurrent requests get the same number.

    Usage:
        from django.db.models import F

        seq = DocumentSequence.objects.select_for_update().get(
            company=company, module='MANUAL_JOURNAL'
        )
        number = seq.next_number
        seq.next_number = F('next_number') + 1
        seq.save(update_fields=['next_number'])
        entry_number = f"{seq.prefix}{str(number).zfill(seq.padding)}"
        # Result: "JE-0001"
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='document_sequences',
    )

    module = models.CharField(
        max_length=30,
        verbose_name='module name',
        help_text='e.g., MANUAL_JOURNAL, SALES_INVOICE, PURCHASE_BILL',
    )

    prefix = models.CharField(
        max_length=10,
        verbose_name='prefix',
        help_text='e.g., "JE-", "INV-", "BILL-"',
    )

    next_number = models.PositiveIntegerField(
        default=1,
        verbose_name='next number',
    )

    padding = models.PositiveIntegerField(
        default=4,
        verbose_name='zero padding',
        help_text='Number of digits. 4 → "0001", 5 → "00001".',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'document sequence'
        verbose_name_plural = 'document sequences'

        constraints = [
            models.UniqueConstraint(
                fields=['company', 'module'],
                name='unique_sequence_per_company_module',
            ),
        ]

    def __str__(self):
        return (
            f"{self.company.name} → {self.module} "
            f"({self.prefix}{str(self.next_number).zfill(self.padding)})"
        )


# ──────────────────────────────────────────────
# CURRENCY EXCHANGE RATE
# ──────────────────────────────────────────────

class CurrencyExchangeRate(models.Model):
    """
    Stores exchange rates for multi-currency transactions.

    Each record says: "On this date, 1 unit of this currency = X units
    of the company's base currency."

    Example for a BDT-based company:
        currency_code: "USD", rate_to_base: 120.00, effective_date: 2026-03-01
        Means: 1 USD = 120 BDT on March 1, 2026

    When creating a transaction, the system looks up the rate for the
    transaction date. If no rate exists for that exact date, it uses the
    most recent rate on or before that date.

    Rates can be entered manually or fetched from an external API.
    The source field tracks where the rate came from.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='exchange_rates',
    )

    currency_code = models.CharField(
        max_length=3,
        verbose_name='currency code',
        help_text='ISO 4217 code (e.g., USD, EUR, GBP).',
    )

    rate_to_base = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name='rate to base currency',
        help_text='1 unit of this currency = X units of base currency.',
    )

    effective_date = models.DateField(
        verbose_name='effective date',
    )

    source = models.CharField(
        max_length=30,
        default='MANUAL',
        verbose_name='source',
        help_text='MANUAL or API provider name.',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'currency exchange rate'
        verbose_name_plural = 'currency exchange rates'
        ordering = ['-effective_date']

        constraints = [
            models.UniqueConstraint(
                fields=['company', 'currency_code', 'effective_date'],
                name='unique_rate_per_currency_per_date',
            ),
        ]

    def __str__(self):
        return (
            f"{self.currency_code} = {self.rate_to_base} "
            f"{self.company.base_currency} ({self.effective_date})"
        )
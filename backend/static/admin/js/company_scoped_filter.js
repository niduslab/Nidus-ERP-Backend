/**
 * Company-Scoped FK Filter for Django Admin (Jazzmin + Select2)
 * 
 * Uses DELEGATED events on $(document) so they survive Select2's
 * DOM replacement. Also listens for select2:select as a fallback.
 */
(function () {
    'use strict';

    var FIELD_MAP = {
        'id_parent': 'classifications_layer2',
        'id_classification': 'classifications_layer3',
        'id_parent_account': 'accounts',
        'id_account': 'accounts',
    };

    function waitForJQuery(callback) {
        if (window.django && window.django.jQuery) {
            callback(window.django.jQuery);
        } else if (window.jQuery) {
            callback(window.jQuery);
        } else {
            setTimeout(function () { waitForJQuery(callback); }, 100);
        }
    }

    function fetchOptions(companyId, $, callback) {
        if (!companyId) { callback(null); return; }
        $.ajax({
            url: '/admin/api/company-options/' + companyId + '/',
            dataType: 'json',
            success: function (data) {
                console.log('[CF] Got:', data.company_name,
                    'L2:', data.classifications_layer2.length,
                    'L3:', data.classifications_layer3.length,
                    'Acc:', data.accounts.length);
                callback(data);
            },
            error: function (xhr, st, err) {
                console.error('[CF] API error:', st, err);
                callback(null);
            }
        });
    }

    function rebuildSelect($, selectId, options) {
        var $sel = $('#' + selectId);
        if ($sel.length === 0) return;

        var currentVal = $sel.val();
        var hasS2 = $sel.hasClass('select2-hidden-accessible');

        if (hasS2) {
            try { $sel.select2('destroy'); } catch (e) {}
        }

        $sel.find('option[value!=""]').remove();
        if ($sel.find('option[value=""]').length === 0) {
            $sel.prepend('<option value="">---------</option>');
        }

        if (options) {
            options.forEach(function (opt) {
                $sel.append($('<option>').val(opt.id).text(opt.label));
            });
        }

        if (currentVal && $sel.find('option[value="' + currentVal + '"]').length > 0) {
            $sel.val(currentVal);
        } else {
            $sel.val('');
        }

        if (hasS2) {
            try {
                $sel.select2({ theme: 'admin-autocomplete', allowClear: true, placeholder: '---------' });
            } catch (e) {
                console.warn('[CF] S2 re-init failed:', selectId, e);
            }
        }

        $sel.trigger('change');
        console.log('[CF] Updated #' + selectId, (options ? options.length : 0), 'opts');
    }

    function applyFilter($, companyId) {
        console.log('[CF] Filtering for company:', companyId);
        if (!companyId) {
            Object.keys(FIELD_MAP).forEach(function (fid) { rebuildSelect($, fid, []); });
            return;
        }
        fetchOptions(companyId, $, function (data) {
            if (!data) return;
            Object.keys(FIELD_MAP).forEach(function (fid) {
                if (data[FIELD_MAP[fid]]) rebuildSelect($, fid, data[FIELD_MAP[fid]]);
            });
        });
    }

    function filterInlines($, companyId) {
        if (!companyId) return;
        var $inlines = $('[id$="-default_tax_account"]');
        if ($inlines.length === 0) return;
        fetchOptions(companyId, $, function (data) {
            if (!data || !data.accounts) return;
            $inlines.each(function () { rebuildSelect($, $(this).attr('id'), data.accounts); });
        });
    }

    function getCompanyVal($) {
        var $sel = $('#id_company');
        if ($sel.length === 0) return null;
        return $sel.val() || null;
    }

    function onCompanyChanged($) {
        var val = getCompanyVal($);
        console.log('[CF] Company changed to:', val);
        if (val) {
            applyFilter($, val);
            filterInlines($, val);
        }
    }

    function init($) {
        var $company = $('#id_company');
        if ($company.length === 0) {
            console.log('[CF] No #id_company — skipping.');
            return;
        }
        console.log('[CF] Init. Value:', $company.val() || '(empty)');

        // METHOD 1: Delegated jQuery change (survives DOM replacement)
        $(document).on('change', '#id_company', function () {
            console.log('[CF] change event (delegated)');
            onCompanyChanged($);
        });

        // METHOD 2: Select2-specific event (delegated)
        $(document).on('select2:select', '#id_company', function () {
            console.log('[CF] select2:select event');
            onCompanyChanged($);
        });

        // METHOD 3: MutationObserver watching the Select2 container
        // Select2 updates a hidden <select>. We watch for attribute changes.
        var observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (m) {
                if (m.type === 'childList' || m.type === 'attributes') {
                    var newVal = getCompanyVal($);
                    if (newVal && newVal !== observer._lastVal) {
                        console.log('[CF] MutationObserver detected change:', newVal);
                        observer._lastVal = newVal;
                        onCompanyChanged($);
                    }
                }
            });
        });
        observer._lastVal = $company.val();

        // Observe the select element for option changes
        if ($company[0]) {
            observer.observe($company[0], { childList: true, attributes: true, subtree: true });
        }

        // Also observe the Select2 container if it exists
        setTimeout(function () {
            var s2Container = $company.next('.select2-container');
            if (s2Container.length) {
                observer.observe(s2Container[0], { childList: true, attributes: true, subtree: true });
                console.log('[CF] Also observing Select2 container');
            }
        }, 500);

        // On page load: filter if company already selected
        var current = $company.val();
        if (current) {
            setTimeout(function () {
                applyFilter($, current);
                filterInlines($, current);
            }, 800);
        }

        // Inline row additions
        $(document).on('formset:added', function () {
            var cid = getCompanyVal($);
            if (cid) setTimeout(function () { filterInlines($, cid); }, 300);
        });
    }

    waitForJQuery(function ($) {
        $(function () {
            setTimeout(function () { init($); }, 300);
        });
    });
})();

import json
import uuid

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .models import FieldSpec, FieldType

_SKIP_TYPES = {"hidden", "submit", "button", "reset", "image"}

_FIELD_EXTRACT_JS = """
() => {
    const results = [];
    const skipTypes = new Set(%s);
    const candidates = document.querySelectorAll('input, select, textarea');
    const radioGroups = new Map(); // name -> [{selector, optionLabel, required}]

    function buildSelector(el) {
        if (el.id) return '#' + CSS.escape(el.id);
        const markerId = 'af-' + Math.random().toString(36).slice(2, 10);
        el.setAttribute('data-agent-field-id', markerId);
        return '[data-agent-field-id="' + markerId + '"]';
    }

    function labelFor(el) {
        let label = '';
        if (el.labels && el.labels.length > 0) {
            label = Array.from(el.labels).map(l => l.textContent.trim()).filter(Boolean).join(' ');
        }
        if (!label) {
            label = (el.getAttribute('aria-label') || '').trim();
        }
        if (!label) {
            const labelledBy = el.getAttribute('aria-labelledby');
            if (labelledBy) {
                label = labelledBy.split(/\\s+/)
                    .map(id => { const n = document.getElementById(id); return n ? n.textContent.trim() : ''; })
                    .filter(Boolean)
                    .join(' ');
            }
        }
        if (!label) {
            label = (el.getAttribute('placeholder') || '').trim();
        }
        if (!label) {
            let node = el.previousSibling;
            let hops = 0;
            while (node && hops < 5 && !label) {
                const text = (node.textContent || '').trim();
                if (text) label = text;
                node = node.previousSibling;
                hops++;
            }
        }
        return label;
    }

    // Radio group label: prefer an enclosing <fieldset><legend>, since that's the
    // standard accessible pattern for "choose one of N" groups (e.g. "Pizza Size").
    // Falls back to a humanized `name` attribute when there's no fieldset.
    function groupLabelFor(el) {
        const fieldset = el.closest('fieldset');
        if (fieldset) {
            const legend = fieldset.querySelector('legend');
            if (legend && legend.textContent.trim()) return legend.textContent.trim();
        }
        return '';
    }

    for (const el of candidates) {
        if (el.disabled) continue;

        const tag = el.tagName.toLowerCase();
        const type = (el.getAttribute('type') || 'text').toLowerCase();
        if (tag === 'input' && skipTypes.has(type)) continue;

        // Radios sharing a `name` are one choose-one field, not N independent ones —
        // grouped below instead of pushed individually.
        if (tag === 'input' && type === 'radio' && el.name) {
            if (!radioGroups.has(el.name)) radioGroups.set(el.name, []);
            radioGroups.get(el.name).push({
                selector: buildSelector(el),
                optionLabel: labelFor(el) || el.value || '',
                groupLabel: groupLabelFor(el),
                required: !!el.required,
            });
            continue;
        }

        const selector = buildSelector(el);
        const label = labelFor(el);

        let fieldType;
        if (tag === 'select') fieldType = 'select';
        else if (tag === 'textarea') fieldType = 'textarea';
        else if (type === 'checkbox') fieldType = 'checkbox';
        else if (type === 'radio') fieldType = 'radio'; // no `name` — can't group, treat standalone
        else if (type === 'file') fieldType = 'file';
        else fieldType = 'text';

        let options = [];
        if (tag === 'select') {
            options = Array.from(el.options).map(o => o.textContent.trim());
        }

        results.push({
            selector: selector,
            label: label,
            field_type: fieldType,
            required: !!el.required,
            options: options,
            option_selectors: {},
            placeholder: el.getAttribute('placeholder') || '',
        });
    }

    for (const [name, opts] of radioGroups.entries()) {
        const groupLabel = (opts.map(o => o.groupLabel).find(Boolean)) ||
            name.replace(/[_-]+/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase());
        const optionSelectors = {};
        for (const o of opts) {
            optionSelectors[o.optionLabel] = o.selector;
        }
        results.push({
            selector: opts[0].selector,
            label: groupLabel,
            field_type: 'radio',
            required: opts.some(o => o.required),
            options: opts.map(o => o.optionLabel),
            option_selectors: optionSelectors,
            placeholder: '',
        });
    }

    return results;
}
""" % (json.dumps(sorted(_SKIP_TYPES)))


def detect_fields(page: Page) -> tuple[list[FieldSpec], list[str]]:
    warnings: list[str] = []

    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightTimeoutError:
        warnings.append("Page never reached networkidle — proceeding with detection anyway")

    fields: list[FieldSpec] = []
    for frame in page.frames:
        try:
            raw_fields = frame.evaluate(_FIELD_EXTRACT_JS)
        except PlaywrightError as e:
            warnings.append(f"Skipped frame '{frame.url}' during detection: {e}")
            continue

        for raw in raw_fields:
            fields.append(
                FieldSpec(
                    marker_id=str(uuid.uuid4()),
                    frame=frame,
                    selector=raw["selector"],
                    label=raw["label"],
                    field_type=FieldType(raw["field_type"]),
                    required=raw["required"],
                    options=raw["options"],
                    option_selectors=raw.get("option_selectors", {}),
                    placeholder=raw["placeholder"],
                )
            )

    return fields, warnings

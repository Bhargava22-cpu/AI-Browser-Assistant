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

    for (const el of candidates) {
        if (el.disabled) continue;

        const tag = el.tagName.toLowerCase();
        const type = (el.getAttribute('type') || 'text').toLowerCase();
        if (tag === 'input' && skipTypes.has(type)) continue;

        let selector;
        if (el.id) {
            selector = '#' + CSS.escape(el.id);
        } else {
            const markerId = 'af-' + Math.random().toString(36).slice(2, 10);
            el.setAttribute('data-agent-field-id', markerId);
            selector = '[data-agent-field-id="' + markerId + '"]';
        }

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

        let fieldType;
        if (tag === 'select') fieldType = 'select';
        else if (tag === 'textarea') fieldType = 'textarea';
        else if (type === 'checkbox') fieldType = 'checkbox';
        else if (type === 'radio') fieldType = 'radio';
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
            placeholder: el.getAttribute('placeholder') || '',
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
                    placeholder=raw["placeholder"],
                )
            )

    return fields, warnings

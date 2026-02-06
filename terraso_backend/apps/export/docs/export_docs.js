/**
 * Shared JavaScript for LandPKS Export Documentation
 *
 * Provides CSV parsing, data loading, and rendering functions for:
 * - CSV format docs
 * - JSON tree structure
 * - JSON field tables
 * - Hierarchy visualization
 */

// =============================================================================
// BOOTSTRAP / INITIALIZATION
// =============================================================================

/**
 * Initialize export docs with dynamic CSS loading and rendering.
 * @param {string} base - Base URL for assets and data (e.g., 'https://example.com/export')
 * @param {string} mode - Render mode: 'csv', 'tree', 'fields', or 'hierarchy'
 * @param {string} prefix - Element ID prefix (e.g., 'csv' for 'csv-loading', 'csv-content')
 * @param {string} [sheetsId] - Optional Google Sheets spreadsheet ID to load CSVs from
 */
function initExportDocs(base, mode, prefix, sheetsId) {
    // Load CSS dynamically
    var css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = base + '/export_docs_wp.css';
    document.head.appendChild(css);

    var loadingEl = document.getElementById(prefix + '-loading');
    var contentEl = document.getElementById(prefix + '-content');

    var dataSource = sheetsId ? 'sheets:' + sheetsId : base;
    loadExportData(dataSource).then(function(data) {
        switch (mode) {
            case 'csv':
                renderCsvDocs(data, contentEl, {showOverview: false});
                break;
            case 'tree':
                renderJsonTree(data, contentEl, {minimal: true});
                break;
            case 'fields':
                renderJsonFields(data, contentEl);
                break;
            case 'hierarchy':
                renderHierarchy(data, contentEl);
                break;
        }
        loadingEl.style.display = 'none';
    }).catch(function(err) {
        loadingEl.innerHTML = 'Error loading: ' + err.message;
    });
}

// =============================================================================
// CSV PARSING
// =============================================================================

function parseCSV(text) {
    const lines = text.trim().replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
    const headers = parseCSVLine(lines[0]);
    return lines.slice(1).filter(line => line.trim()).map(line => {
        const values = parseCSVLine(line);
        const obj = {};
        headers.forEach((h, i) => obj[h] = values[i] || '');
        return obj;
    });
}

function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"') {
            if (inQuotes && line[i + 1] === '"') {
                current += '"';
                i++;
            } else {
                inQuotes = !inQuotes;
            }
        } else if (char === ',' && !inQuotes) {
            result.push(current);
            current = '';
        } else {
            current += char;
        }
    }
    result.push(current);
    return result;
}

// =============================================================================
// DATA LOADING
// =============================================================================

async function loadExportData(basePath = '') {
    // Check if using Google Sheets (format: "sheets:SPREADSHEET_ID")
    if (basePath.startsWith('sheets:')) {
        const spreadsheetId = basePath.slice(7);
        const sheetBase = 'https://docs.google.com/spreadsheets/d/' + spreadsheetId + '/gviz/tq?tqx=out:csv&sheet=';
        const [sheetsObjRes, sheetsFieldsRes, sheetsEnumRes] = await Promise.all([
            fetch(sheetBase + 'objects'),
            fetch(sheetBase + 'fields'),
            fetch(sheetBase + 'enum_values')
        ]);
        return {
            objects: parseCSV(await sheetsObjRes.text()),
            fields: parseCSV(await sheetsFieldsRes.text()),
            enumValues: parseCSV(await sheetsEnumRes.text())
        };
    }

    // Default: backend-hosted CSVs
    const prefix = basePath ? basePath + '/' : '';
    const [objectsRes, fieldsRes, enumValuesRes] = await Promise.all([
        fetch(`${prefix}objects.csv`),
        fetch(`${prefix}fields.csv`),
        fetch(`${prefix}enum_values.csv`)
    ]);
    return {
        objects: parseCSV(await objectsRes.text()),
        fields: parseCSV(await fieldsRes.text()),
        enumValues: parseCSV(await enumValuesRes.text())
    };
}

// =============================================================================
// UTILITIES
// =============================================================================

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function groupBy(arr, keyFn) {
    const result = {};
    for (const item of arr) {
        const key = typeof keyFn === 'string' ? item[keyFn] : keyFn(item);
        if (!result[key]) result[key] = [];
        result[key].push(item);
    }
    return result;
}

function buildParentMap(fields, objectNames) {
    const parentMap = {};
    for (const field of fields) {
        const ftype = field.type || '';
        const fname = field.json_name || '';
        const parentObj = field.object || '';
        if (!fname) continue;
        const isArray = ftype.endsWith('[]');
        const baseType = isArray ? ftype.slice(0, -2) : ftype;
        if (objectNames.has(baseType)) {
            parentMap[baseType] = { parent: parentObj, field: fname, isArray };
        }
    }
    return parentMap;
}

function computeJsonPath(objName, parentMap) {
    if (objName === 'Site' || objName === 'Location') return 'sites[]';
    if (!parentMap[objName]) return '';
    const { parent, field, isArray } = parentMap[objName];
    const parentPath = computeJsonPath(parent, parentMap);
    return `${parentPath}.${field}${isArray ? '[]' : ''}`;
}

// =============================================================================
// CSV FORMAT RENDERER
// =============================================================================

function getCsvSections(data) {
    const { fields } = data;

    // Get unique csv_sections that have CSV columns, in order of first appearance
    const csvFields = fields.filter(f => f.csv_column);
    const seen = new Set();
    const sections = [];
    for (const f of csvFields) {
        const section = f.csv_section;
        if (section && !seen.has(section)) {
            seen.add(section);
            sections.push(section);
        }
    }
    return sections;
}

function toSlug(name) {
    return name.toLowerCase().replace(/\s+/g, '-');
}

function renderCsvNav(data, container, jsonFormatHref = '/json-export-format/') {
    const { objects } = data;
    const sections = getCsvSections(data);

    let html = '<a href="#overview">Overview</a> ';
    for (const name of sections) {
        const objInfo = objects.find(o => o.name === name);
        const displayName = (objInfo && objInfo.label) || name;
        html += `<a href="#csv-${toSlug(name)}">${escapeHtml(displayName)}</a> `;
    }
    html += `<span class="muted" style="margin-left: 1em;">See also: <a href="${jsonFormatHref}">JSON Format</a></span>`;
    container.innerHTML = html;
}

function renderCsvDocs(data, container, options = {}) {
    const { objects, fields, enumValues } = data;
    const { showOverview = true } = options;

    // Group enum values by enum (use labels for CSV)
    const valuesByEnum = groupBy(enumValues, 'enum');

    // Get fields with CSV columns, grouped by csv_section
    const csvFields = fields.filter(f => f.csv_column);
    const fieldsBySection = groupBy(csvFields, 'csv_section');
    const sections = getCsvSections(data);

    let html = '';
    if (showOverview) {
        html += `<div class="section" id="overview">
            <h2>Overview</h2>
            <p>The CSV export produces <strong>one row per depth interval per site</strong>. Site-level fields repeat on each row.</p>
        </div>`;
    }

    for (const name of sections) {
        const sectionFields = fieldsBySection[name] || [];
        if (!sectionFields.length) continue;

        let tableRows = '';
        for (const f of sectionFields) {
            const csvCol = f.csv_column || '';
            const ftype = f.type || '';
            const fdesc = f.description || '';

            let typeHtml;
            if (valuesByEnum[ftype]) {
                const vals = valuesByEnum[ftype].map(v => escapeHtml(v.label));
                typeHtml = vals.join(', ');
            } else if (ftype === 'boolean') {
                typeHtml = 'TRUE, FALSE';
            } else {
                typeHtml = escapeHtml(ftype);
            }

            tableRows += `<tr><td>${escapeHtml(csvCol)}</td><td>${typeHtml}</td><td>${escapeHtml(fdesc)}</td></tr>`;
        }

        const objInfo = objects.find(o => o.name === name);
        const displayName = (objInfo && objInfo.label) || name;
        const descHtml = objInfo && objInfo.description
            ? `<p class="description">${escapeHtml(objInfo.description)}</p>`
            : '';

        html += `<div class="section" id="csv-${toSlug(name)}">
            <h2>${escapeHtml(displayName)}</h2>
            ${descHtml}
            <table>
                <thead><tr><th>Column</th><th>Type</th><th>Description</th></tr></thead>
                <tbody>${tableRows}</tbody>
            </table>
        </div>`;
    }

    container.innerHTML = html;
}

// =============================================================================
// JSON TREE RENDERER
// =============================================================================

function buildJsonTree(data) {
    const { objects, fields } = data;
    const objectNames = new Set(objects.map(o => o.name));

    // Build children map: parent -> [{field, childType, isArray}]
    const children = {};
    for (const f of fields) {
        const fname = f.json_name;
        const ftype = f.type || '';
        const parent = f.object;
        if (!fname) continue;

        const isArray = ftype.endsWith('[]');
        const baseType = isArray ? ftype.slice(0, -2) : ftype;

        if (objectNames.has(baseType)) {
            if (!children[parent]) children[parent] = [];
            children[parent].push({ field: fname, childType: baseType, isArray });
        }
    }
    return children;
}

function renderJsonTree(data, container, options = {}) {
    const children = buildJsonTree(data);
    const { minimal = false } = options;

    const link = (name, obj, isArray = false) =>
        `<a href="#obj-${toSlug(obj)}">${name}${isArray ? '[]' : ''}</a>`;

    function renderNode(objName, fieldName, isArray, indent) {
        const prefix = '  '.repeat(indent);
        let html = prefix + link(fieldName, objName, isArray);

        const objChildren = children[objName] || [];
        for (const child of objChildren) {
            html += '\n' + renderNode(child.childType, child.field, child.isArray, indent + 1);
        }
        return html;
    }

    const structureHtml = renderNode('Site', 'sites', true, 0);

    if (minimal) {
        container.innerHTML = `<pre><code>${structureHtml}</code></pre>`;
    } else {
        container.innerHTML = `
            <h2>JSON Structure</h2>
            <p>The export API returns site data with the following structure. Click field names to jump to documentation.</p>
            <pre><code>${structureHtml}</code></pre>
            <p>Fields starting with <code>_</code> are derived fields expanded by the export.</p>
        `;
    }
}

// =============================================================================
// JSON FIELDS RENDERER
// =============================================================================

function renderJsonFields(data, container) {
    const { objects, fields, enumValues } = data;
    const objectNames = new Set(objects.map(o => o.name));

    // Group fields by object
    const fieldsByObject = groupBy(fields, 'object');

    // Group enum values
    const valuesByEnum = groupBy(enumValues, 'enum');

    const parentMap = buildParentMap(fields, objectNames);
    const isJsonField = f => !!f.json_name;

    // Filter objects with JSON fields
    const jsonObjects = objects.filter(obj => {
        if (obj.name === 'Location') return false;
        const objFields = fieldsByObject[obj.name] || [];
        return objFields.some(isJsonField);
    });

    let html = '';

    for (const obj of jsonObjects) {
        const name = obj.name;
        const desc = obj.description || '';
        const path = computeJsonPath(name, parentMap);
        const objFields = (fieldsByObject[name] || []).filter(isJsonField);

        if (!objFields.length) continue;

        let tableRows = '';
        for (const f of objFields) {
            const fname = f.json_name || '';
            const ftype = f.type || '';
            const fdesc = f.description || '';

            const isArray = ftype.endsWith('[]');
            const baseType = isArray ? ftype.slice(0, -2) : ftype;
            const fnameHtml = `<code>${escapeHtml(fname)}${isArray ? '[]' : ''}</code>`;

            let typeHtml;
            if (valuesByEnum[baseType]) {
                const vals = valuesByEnum[baseType].map(v => {
                    const val = escapeHtml(v.value);
                    const desc = v.description ? ` (${escapeHtml(v.description)})` : '';
                    return val + desc;
                });
                typeHtml = vals.join(', ');
            } else if (baseType === 'boolean') {
                typeHtml = 'true, false';
            } else if (baseType === 'datetime') {
                typeHtml = 'ISO 8601 DateTime';
            } else if (objectNames.has(baseType)) {
                typeHtml = `<a href="#obj-${toSlug(baseType)}">${escapeHtml(baseType)}</a>`;
            } else {
                typeHtml = escapeHtml(baseType);
            }

            tableRows += `<tr><td>${fnameHtml}</td><td>${typeHtml}</td><td>${escapeHtml(fdesc)}</td></tr>`;
        }

        html += `<div class="section" id="obj-${toSlug(name)}">
            <h2>${escapeHtml(name)}</h2>
            ${desc ? `<p class="description">${escapeHtml(desc)}</p>` : ''}
            ${path ? `<p class="muted">JSON path: <code>${escapeHtml(path)}</code></p>` : ''}
            <table>
                <thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead>
                <tbody>${tableRows}</tbody>
            </table>
        </div>`;
    }

    container.innerHTML = html;
}

// =============================================================================
// HIERARCHY RENDERER (nested boxes)
// =============================================================================

function renderHierarchy(data, container) {
    const { objects, fields, enumValues } = data;
    const objectNames = new Set(objects.map(o => o.name));
    const objectDesc = Object.fromEntries(objects.map(o => [o.name, o.description]));

    // Group enum values
    const valuesByEnum = {};
    for (const val of enumValues) {
        const enumName = val.enum || '';
        if (!valuesByEnum[enumName]) valuesByEnum[enumName] = [];
        valuesByEnum[enumName].push(val);
    }

    // Build children and primitives maps
    const children = {};
    const primitives = {};

    for (const field of fields) {
        const ftype = field.type || '';
        const fname = field.json_name || '';
        const parent = field.object || '';
        const fdesc = field.description || '';

        if (!fname) continue;

        const isArray = ftype.endsWith('[]');
        const baseType = isArray ? ftype.slice(0, -2) : ftype;

        if (objectNames.has(baseType)) {
            if (!children[parent]) children[parent] = [];
            children[parent].push({ fname, childType: baseType, isArray });
        } else {
            // Compute display type
            let typeDisplay;
            if (valuesByEnum[baseType]) {
                typeDisplay = valuesByEnum[baseType].map(v => {
                    const val = v.value || '';
                    const desc = v.description ? ` (${v.description})` : '';
                    return val + desc;
                }).join(', ');
            } else if (baseType === 'boolean') {
                typeDisplay = 'true, false';
            } else if (baseType === 'datetime') {
                typeDisplay = 'ISO 8601 DateTime';
            } else {
                typeDisplay = baseType;
            }

            if (!primitives[parent]) primitives[parent] = [];
            primitives[parent].push({ fname, typeDisplay, fdesc });
        }
    }

    // Color palette
    const colors = ['#e8f5e9', '#fff3e0', '#e3f2fd', '#fce4ec', '#f3e5f5', '#e0f7fa', '#fff8e1', '#efebe9'];
    const borderColors = ['#4caf50', '#ff9800', '#2196f3', '#e91e63', '#9c27b0', '#00bcd4', '#ffc107', '#795548'];

    function renderNode(objName, fieldName = null, isArray = false, depth = 0) {
        const color = colors[depth % colors.length];
        const border = borderColors[depth % borderColors.length];
        const desc = objectDesc[objName] || '';

        let label = fieldName || objName;
        if (isArray) label += '[]';

        // Primitive fields table
        let fieldsHtml = '';
        if (primitives[objName]) {
            const rows = primitives[objName].map(p =>
                `<tr><td class="pfield-name">${escapeHtml(p.fname)}</td>` +
                `<td class="pfield-type">${escapeHtml(p.typeDisplay)}</td>` +
                `<td class="pfield-desc">${escapeHtml(p.fdesc)}</td></tr>`
            ).join('');
            fieldsHtml = `<table class="fields">${rows}</table>`;
        }

        // Child objects
        let childHtml = '';
        if (children[objName]) {
            const items = children[objName].map(c =>
                renderNode(c.childType, c.fname, c.isArray, depth + 1)
            ).join('');
            childHtml = `<div class="children">${items}</div>`;
        }

        return `<div class="node" style="background: ${color}; border-color: ${border};">
            <div class="header">
                <span class="field-name">${label}</span>
                <span class="type-name">${objName}</span>
            </div>
            ${desc ? `<div class="desc">${escapeHtml(desc)}</div>` : ''}
            ${fieldsHtml}
            ${childHtml}
        </div>`;
    }

    container.innerHTML = renderNode('Site', 'sites', true, 0);
}

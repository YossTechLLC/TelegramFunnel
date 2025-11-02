# GCRegister10-26 Modification Guide - Threshold Payout UI

**Created:** 2025-10-28
**Purpose:** Add threshold payout configuration to registration form

---

## Overview

This guide details the changes needed to GCRegister10-26 to support threshold payout configuration during channel registration.

**Key Changes:**
1. Add payout strategy dropdown to forms.py
2. Add threshold amount field to forms.py
3. Update register.html template with new fields and JavaScript
4. Update tpr10-26.py to save threshold fields to database

---

## File 1: forms.py

**Location:** `OCTOBER/10-26/GCRegister10-26/forms.py`

### Add New Imports

At the top of the file, ensure you have:

```python
from wtforms import SelectField, DecimalField
from wtforms.validators import Optional, NumberRange
```

### Add New Fields to ChannelRegistrationForm

Find the `ChannelRegistrationForm` class and add these fields **before** the `submit` field:

```python
# NEW FIELDS for threshold payout (add after client_payout_network)

payout_strategy = SelectField(
    'Payout Strategy',
    choices=[
        ('instant', 'Instant Payout (Recommended for most currencies)'),
        ('threshold', 'Threshold Payout (For high-fee currencies like Monero)')
    ],
    default='instant',
    validators=[DataRequired()],
    description='Choose how you want to receive payouts'
)

payout_threshold_usd = DecimalField(
    'Payout Threshold (USD)',
    validators=[
        Optional(),
        NumberRange(min=50, message='Minimum threshold is $50')
    ],
    description='Minimum amount to accumulate before payout (recommended: $100-500 for Monero)',
    default=0,
    places=2
)
```

### Add Custom Validator

Add this method to the `ChannelRegistrationForm` class:

```python
def validate_payout_threshold_usd(form, field):
    """Validate threshold based on strategy."""
    if form.payout_strategy.data == 'threshold':
        if not field.data or field.data <= 0:
            raise ValidationError(
                'Payout threshold is required when using threshold strategy. Minimum $50.'
            )
```

---

## File 2: register.html

**Location:** `OCTOBER/10-26/GCRegister10-26/templates/register.html`

### Add Payout Strategy Section

Find the section with `client_payout_network` field and add this **after** it:

```html
<!-- Payout Strategy Section -->
<div class="form-group">
    <h4>💰 Payout Configuration</h4>
    <p class="text-muted">Configure when and how you receive payments from subscriptions</p>
</div>

<div class="form-group">
    {{ form.payout_strategy.label(class="form-label") }}
    {{ form.payout_strategy(class="form-control", id="payout_strategy") }}
    {% if form.payout_strategy.errors %}
        <div class="text-danger">
            {% for error in form.payout_strategy.errors %}
                <small>{{ error }}</small>
            {% endfor %}
        </div>
    {% endif %}
    <small class="form-text text-muted">
        <strong>Instant:</strong> Payouts processed immediately after each subscription (best for BTC, LTC, DOGE).<br>
        <strong>Threshold:</strong> Payouts batched until accumulated amount reaches threshold (best for XMR to minimize fees).
    </small>
</div>

<div class="form-group" id="threshold-amount-group" style="display: none;">
    {{ form.payout_threshold_usd.label(class="form-label") }}
    <div class="input-group">
        <div class="input-group-prepend">
            <span class="input-group-text">$</span>
        </div>
        {{ form.payout_threshold_usd(class="form-control", placeholder="e.g., 500") }}
    </div>
    {% if form.payout_threshold_usd.errors %}
        <div class="text-danger">
            {% for error in form.payout_threshold_usd.errors %}
                <small>{{ error }}</small>
            {% endfor %}
        </div>
    {% endif %}
    <small class="form-text text-muted">
        {{ form.payout_threshold_usd.description }}
    </small>
</div>
```

### Add JavaScript for Show/Hide Logic

Add this **before** the closing `</body>` tag:

```html
<script>
// Show/hide threshold field based on strategy selection
function toggleThresholdField() {
    const strategySelect = document.getElementById('payout_strategy');
    const thresholdGroup = document.getElementById('threshold-amount-group');

    if (strategySelect && thresholdGroup) {
        if (strategySelect.value === 'threshold') {
            thresholdGroup.style.display = 'block';
        } else {
            thresholdGroup.style.display = 'none';
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    const strategySelect = document.getElementById('payout_strategy');
    if (strategySelect) {
        // Set initial state
        toggleThresholdField();

        // Add change listener
        strategySelect.addEventListener('change', toggleThresholdField);
    }
});
</script>
```

---

## File 3: tpr10-26.py

**Location:** `OCTOBER/10-26/GCRegister10-26/tpr10-26.py`

### Modify Database Insertion

Find the section where channel data is inserted into `main_clients_database` (around line 200-250).

**Add these fields to the INSERT statement:**

```python
# Find the INSERT INTO main_clients_database section
# Add these new fields to the column list:

# ... existing columns ...,
payout_strategy,
payout_threshold_usd,
payout_threshold_updated_at

# And add these to the VALUES:

# ... existing values ...,
%s,  # payout_strategy
%s,  # payout_threshold_usd
NOW()  # payout_threshold_updated_at
```

**Add these to the parameters tuple:**

```python
# Find the parameters tuple for the INSERT statement
# Add these values:

# ... existing parameters ...,
form.payout_strategy.data,
form.payout_threshold_usd.data if form.payout_strategy.data == 'threshold' else 0
```

### Example of Modified INSERT

```python
# Complete example of how the insert should look:
insert_query = """
    INSERT INTO main_clients_database (
        open_channel_id,
        channel_link,
        tier_1_price, tier_1_days,
        tier_2_price, tier_2_days,
        tier_3_price, tier_3_days,
        client_payout_currency,
        client_payout_network,
        client_wallet_address,
        payout_strategy,
        payout_threshold_usd,
        payout_threshold_updated_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
    )
"""

insert_params = (
    form.open_channel_id.data,
    form.channel_link.data,
    form.tier_1_price.data,
    form.tier_1_days.data,
    form.tier_2_price.data,
    form.tier_2_days.data,
    form.tier_3_price.data,
    form.tier_3_days.data,
    form.client_payout_currency.data,
    form.client_payout_network.data,
    form.client_wallet_address.data,
    form.payout_strategy.data,
    form.payout_threshold_usd.data if form.payout_strategy.data == 'threshold' else 0
)
```

---

## Testing Checklist

After making these changes, test the following:

### 1. Form Rendering
- [ ] Payout strategy dropdown appears on registration form
- [ ] Default selection is "Instant Payout"
- [ ] Threshold amount field is initially hidden

### 2. JavaScript Functionality
- [ ] Selecting "Threshold Payout" shows threshold amount field
- [ ] Selecting "Instant Payout" hides threshold amount field
- [ ] Field toggle works on page load if form has errors (re-render)

### 3. Form Validation
- [ ] Submitting with strategy='instant' works without threshold
- [ ] Submitting with strategy='threshold' and empty threshold shows error
- [ ] Submitting with strategy='threshold' and threshold < $50 shows error
- [ ] Submitting with strategy='threshold' and threshold >= $50 works

### 4. Database Insertion
- [ ] New channels with strategy='instant' save correctly (threshold=0)
- [ ] New channels with strategy='threshold' save with correct threshold
- [ ] `payout_threshold_updated_at` is set to NOW()

### 5. Integration Testing
- [ ] Register channel with instant payout
- [ ] Make test payment → verify routed to GCSplit1
- [ ] Register channel with threshold payout ($500)
- [ ] Make test payment → verify routed to GCAccumulator
- [ ] Check payout_accumulation table for USDT record

---

## Example Screenshots (Expected UI)

### Strategy Selection

```
┌─────────────────────────────────────────────┐
│ Payout Strategy                             │
│ ┌─────────────────────────────────────────┐ │
│ │ Instant Payout (Recommended for most... ▼│ │
│ └─────────────────────────────────────────┘ │
│ Instant: Payouts processed immediately       │
│ after each subscription (best for BTC).      │
│ Threshold: Payouts batched until amount      │
│ reaches threshold (best for XMR).            │
└─────────────────────────────────────────────┘
```

### Threshold Field (When Visible)

```
┌─────────────────────────────────────────────┐
│ Payout Threshold (USD)                      │
│ ┌───┬──────────────────────────────────────┐│
│ │ $ │ 500                                  ││
│ └───┴──────────────────────────────────────┘│
│ Minimum amount to accumulate before payout   │
│ (recommended: $100-500 for Monero)           │
└─────────────────────────────────────────────┘
```

---

## Related Files

- `DB_MIGRATION_THRESHOLD_PAYOUT.md` - Database schema changes
- `IMPLEMENTATION_SUMMARY.md` - Overall implementation guide
- `MAIN_ARCHITECTURE_WORKFLOW.md` - Implementation tracker

---

## Notes

- **Backward Compatibility:** All existing channels will default to `payout_strategy='instant'` after migration
- **Validation:** Threshold minimum is $50 to ensure batch fees are economical
- **Currency Recommendation:** Threshold payout is primarily designed for high-fee currencies like Monero (XMR)
- **User Experience:** JavaScript provides instant feedback without page refresh

---

**Status:** Implementation Guide Complete
**Next Step:** Apply these changes to GCRegister10-26 files

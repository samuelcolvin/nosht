import React from 'react'
import {
  FormGroup,
  Label as BsLabel,
  Input as BsInput,
  CustomInput,
  FormText,
  FormFeedback,
  InputGroup,
  InputGroupAddon,
  Button,
  InputGroupButtonDropdown,
  DropdownToggle,
  DropdownMenu,
  DropdownItem
} from 'reactstrap'
import DatePicker from 'react-datepicker'
import moment from 'moment'
import {as_title, on_mobile} from '../utils'
import Map from '../general/Map'
import Editor from '../editor'

const Label = ({field, children}) => (
  field.show_label !== false ? (
    <BsLabel for={field.name} className={field.required ? 'required' : ''}>
     { children}
      {field.title}
    </BsLabel>
  ) : null
)

const HelpText = ({field}) => (
  field.help_text ? <FormText>{field.help_text} {field.required && <span>(required)</span>}</FormText> : null
)

const placeholder = field => {
  if (field.placeholder === true) {
    return field.title
  } else if (field.placeholder) {
    return field.placeholder
  }
  return null
}

const GeneralInput = ({className, field, error, disabled, value, onChange, custom_type, ...extra}) => (
  <FormGroup className={className || field.className}>
    <Label field={field}/>
    <BsInput type={custom_type || field.type || 'text'}
             invalid={!!error}
             disabled={disabled}
             name={field.name}
             id={field.name}
             required={field.required}
             maxLength={field.max_length || 255}
             placeholder={placeholder(field)}
             value={value || ''}
             onChange={e => onChange(e.target.value)}
             {...extra}/>
    {error && <FormFeedback>{error}</FormFeedback>}
    <HelpText field={field}/>
  </FormGroup>
)

const MdInput = ({className, field, error, disabled, value, onChange, custom_type, ...extra}) => (
  on_mobile ? (
    <GeneralInput
      custom_type="textarea"
      className={className}
      field={field}
      error={error}
      disabled={disabled}
      value={value}
      onChange={onChange}
      {...extra}
    />
  ) : (
    <FormGroup className={className || field.className}>
      <Label field={field}/>
      <Editor invalid={!!error}
              disabled={disabled}
              id={field.name}
              required={field.required}
              placeholder={placeholder(field)}
              value={value}
              onChange={md => onChange(md)}/>
      {error && <FormFeedback className="d-block">{error}</FormFeedback>}
      <HelpText field={field}/>
    </FormGroup>
  )
)

const Checkbox = ({className, field, disabled, value, onChange}) => (
  <FormGroup className={className || 'py-2'} check>
    <Label field={field}>
      <BsInput type="checkbox"
               label={field.title}
               disabled={disabled}
               name={field.name}
               id={field.name}
               required={field.required}
               checked={value || false}
               onChange={e => onChange(e.target.checked)}/>
    </Label>
    <HelpText field={field}/>
  </FormGroup>
)

const Select = ({className, field, disabled, value, onChange}) => (
  <FormGroup className={className}>
    <Label field={field}/>
    <CustomInput type="select"
                 value={value || ''}
                 disabled={disabled}
                 name={field.name}
                 id={field.name}
                 required={field.required}
                 onChange={e => onChange(e.target.value)}>
      <option value="">&mdash;</option>
      {field.choices && field.choices.map((choice, i) => (
        <option key={i} value={choice.value}>
          {choice.display_name || as_title(choice.value)}
        </option>
      ))}
    </CustomInput>
    <HelpText field={field}/>
  </FormGroup>
)

const IntegerInput = props => (
  <GeneralInput {...props} custom_type="number" step="1" min={props.field.min} max={props.field.max}
                onChange={v => props.onChange(v ? parseInt(v) : null)}/>
)

const NumberInput = props => (
  <GeneralInput {...props} custom_type="number" step={props.field.step} min={props.field.min} max={props.field.max}
                onChange={v => props.onChange(v ? parseFloat(v) : null)}/>
)

const UrlInput = props => <GeneralInput {...props} onChange={v => props.onChange(v || null)}/>

const DURATIONS = [
  {value: null, title: 'All Day'},
  {value: 1800, title: '30 mins'},
  {value: 3600, title: '1 hour'},
  {value: 3600 * 2, title: '2 hours'},
  {value: 3600 * 3, title: '3 hours'},
  {value: 3600 * 4, title: '4 hours'},
  {value: 3600 * 6, title: '6 hours'},
  {value: 3600 * 8, title: '8 hours'},
]
const browse_tz = Intl.DateTimeFormat().resolvedOptions().timeZone
const midnight = dt => dt && dt.hours() === 0 && dt.minutes() === 0

class DatetimeInput extends React.Component {
  constructor (props) {
    super(props)
    this.state = {drop_open: false}
    this.onDtChange = this.onDtChange.bind(this)
    this.onDurChange = this.onDurChange.bind(this)
  }

  onDtChange (dt, dur) {
    if (dt) {
      if (midnight(dt)) {
        dt = dt.hours(moment().hours())
      }
      this.props.onChange({dt: dt.format(), dur, tz: browse_tz})
    }
  }

  onDurChange (dt, dur) {
    if (dur !== null && midnight(dt)) {
      dt = dt.hours(moment().hours())
    }
    this.props.onChange({dt: dt && dt.format(), dur, tz: browse_tz})
  }

  render () {
    const field = this.props.field
    const duration = this.props.value ? this.props.value.dur : 3600
    const dt = this.props.value && this.props.value.dt ? moment(this.props.value.dt) : null
    const all_day = !duration
    // TODO could use native data picker if on_mobile
    return (
      <FormGroup className={this.props.className}>
        <Label field={field}/>
        <InputGroup>
          <DatePicker
            selected={dt}
            disabled={this.props.disabled}
            onChange={m => this.onDtChange(m, duration)}
            minTime={moment().hours(8).minutes(0)}
            maxTime={moment().hours(23).minutes(0)}
            showTimeSelect={!all_day}
            timeFormat="LT"
            required={field.required}
            dateFormat={all_day ? 'LL' : 'LLL'}
            placeholderText={all_day ? 'Click to select a date' : 'Click to select a date and time'}
            className="form-control"/>
          <InputGroupButtonDropdown
              addonType="append"
              isOpen={this.state.drop_open}
              toggle={() => this.setState({drop_open: !this.state.drop_open})}>
            <DropdownToggle caret className="duration-input">
              Duration ({DURATIONS.find(d => d.value === duration).title})
            </DropdownToggle>
            <DropdownMenu>
             {DURATIONS.map((d, i) => (
                <DropdownItem
                    key={i}
                    active={d.value === duration}
                    onClick={() => this.onDurChange(dt, d.value)}>
                  {d.title}
                </DropdownItem>
             ))}
            </DropdownMenu>
          </InputGroupButtonDropdown>
        </InputGroup>
        <HelpText field={this.props.field}/>
      </FormGroup>
    )
  }
}

class GeoLocation extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      address: typeof(this.props.value) === 'object' ? this.props.value.name : '',
      error: null,
      marker_moved: false,
    }
    this.update = this.update.bind(this)
    this.search = this.search.bind(this)
  }

  geocode (lookup) {
    return new Promise((resolve, reject) => {
      window.gmaps_geocoder.geocode(lookup, (results, status) => {
        if (status === 'OK') {
          resolve(results[0])
        } else {
          reject()
        }
      })
    })
  }

  async search () {
    if (!this.state.address) {
      return
    }
    let latlng
    try {
      const loc = await this.geocode({'address': this.state.address, 'region': 'gb'})
      latlng = loc.geometry.location
    } catch (e) {
      this.setState({error: 'location not found'})
      this.props.onChange(null)
      return
    }
    this.setState({marker_moved: false})
    this.update(latlng, this.state.address)
  }

  async onDrag (e) {
    let address
    if (!this.state.address) {
      try {
        const loc = await this.geocode({'location': e.latLng})
        address = loc.formatted_address
      } catch (e) {
        this.setState({error: 'location not found'})
        this.props.onChange(null)
        return
      }
      this.setState({address, marker_moved: false})
    } else {
      this.setState({marker_moved: true})
      address = this.state.address
    }
    this.update(e.latLng, address)
  }

  async update_address () {
    const loc = await this.geocode({'location': this.props.value})
    this.setState({address: loc.formatted_address, marker_moved: false})
  }

  update (loc, address) {
    this.props.onChange({lat: loc.lat(), lng: loc.lng(), name: address})
    this.setState({error: null})
  }

  on_key_press (e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      this.search()
    }
  }

  on_input_change (e) {
    const v = e.target.value
    this.setState({address: v, marker_moved: v === '' && this.props.value && this.props.value.lat})
  }

  render () {
    const field = this.props.field
    const loc = this.props.value || {lat: null, lng: null, name: null, zoom: null}
    // NOTE: this is hardcoded as central london for now
    loc.lat = loc.lat || 51.507382
    loc.lng = loc.lng || -0.127654
    loc.name = loc.name || ''
    loc.zoom = loc.zoom || 14
    const error = this.state.error || this.props.error
    return (
      <FormGroup className={this.props.className}>
        <Label field={field}/>
        <InputGroup>
          <BsInput type="text"
                   invalid={!!error}
                   disabled={this.props.disabled}
                   required={field.required}
                   placeholder={placeholder(field)}
                   value={this.state.address || ''}
                   onKeyPress={this.on_key_press.bind(this)}
                   onChange={this.on_input_change.bind(this)}/>
          <InputGroupAddon addonType="append">
            <Button onClick={this.search}>Search</Button>
          </InputGroupAddon>
        </InputGroup>
        <HelpText field={field}/>
        <div style={{height: 20}}>
          {this.state.marker_moved &&
            <Button onClick={this.update_address.bind(this)} color="link" className="small-link">
              Update address from marker
            </Button>
          }
        </div>
        <Map geolocation={loc} onDrag={this.onDrag.bind(this)}/>
        {error && <FormFeedback className="d-block">{error}</FormFeedback>}
      </FormGroup>
    )
  }
}

const INPUT_LOOKUP = {
  md: MdInput,
  bool: Checkbox,
  select: Select,
  datetime: DatetimeInput,
  integer: IntegerInput,
  number: NumberInput,
  url: UrlInput,
  geolocation: GeoLocation,
}

const Input = props => {
  const InputComp = INPUT_LOOKUP[props.field.type] || GeneralInput
  props.field.title = props.field.title || as_title(props.field.name)
  const value = [null, undefined].includes(props.value) ? props.field.default : props.value
  return <InputComp field={props.field}
                    error={props.error}
                    value={value}
                    disabled={props.disabled}
                    onChange={props.onChange}/>
}

export default Input

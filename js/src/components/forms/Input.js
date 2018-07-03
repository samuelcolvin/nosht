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
import {as_title} from '../../utils'
import Map from '../utils/Map'

const Label = ({field, children}) => (
  <BsLabel for={field.name} className={field.required && 'required'}>
    {children}
    {field.title}
  </BsLabel>
)

const HelpText = ({field}) => (
  <FormText>{field.help_text} {field.required && <span>(required)</span>}</FormText>
)

const GeneralInput = ({field, error, disabled, value, onChange, custom_type, step}) => (
  <FormGroup>
    <Label field={field}/>
    <BsInput type={custom_type || field.type || 'text'}
             invalid={!!error}
             disabled={disabled}
             step={step || null}
             name={field.name}
             id={field.name}
             required={field.required}
             maxLength={field.max_length || 255}
             placeholder={field.placeholder}
             value={value || ''}
             onChange={e => onChange(e.target.value)}/>
    {error && <FormFeedback>{error}</FormFeedback>}
    <HelpText field={field}/>
  </FormGroup>
)

const Checkbox = ({field, disabled, value, onChange}) => (
  <FormGroup className="py-2" check>
    <Label field={field}>
      <BsInput type="checkbox"
               label={field.title}
               disabled={disabled}
               name={field.name}
               required={field.required}
               checked={value || false}
               onChange={e => onChange(e.target.checked)}/>
    </Label>
    <HelpText field={field}/>
  </FormGroup>
)

const Select = ({field, disabled, value, onChange}) => (
  <FormGroup>
    <Label field={field}/>
    <CustomInput type="select"
                 disabled={disabled}
                 name={field.name}
                 id={field.name}
                 required={field.required}
                 onChange={e => onChange(e.target.value)}>
      <option value="">---------</option>
      {field.choices && field.choices.map((choice, i) => (
        <option key={i} value={choice.value}>
          {/*TODO set selected*/}
          {choice.display_name || choice.value}
        </option>
      ))}
    </CustomInput>
    <HelpText field={field}/>
  </FormGroup>
)

const IntegerInput = props => (
  <GeneralInput {...props} custom_type="number" step="1"/>
)

const DURATIONS = [
  {value: null, title: 'All Day'},
  {value: 1800, title: '30 minutes'},
  {value: 3600 * 1, title: '1 hour'},
  {value: 3600 * 2, title: '2 hours'},
  {value: 3600 * 3, title: '3 hours'},
  {value: 3600 * 4, title: '4 hours'},
  {value: 3600 * 6, title: '6 hours'},
  {value: 3600 * 8, title: '8 hours'},
]

class DatetimeInput extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      duration: null,
      drop_open: false,
    }
  }

  render () {
    const field = this.props.field
    const all_day = !this.state.duration
    return (
      <FormGroup>
        <Label field={field}/>
        <InputGroup>
          <DatePicker
            selected={this.props.value && moment(this.props.value.dt)}
            disabled={this.props.disabled}
            onChange={m => this.props.onChange(m && {dt: m.format(), dur: this.state.duration})}
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
            <DropdownToggle caret>
              Duration ({DURATIONS.find(d => d.value === this.state.duration).title})
            </DropdownToggle>
            <DropdownMenu>
             {DURATIONS.map((d, i) => (
                <DropdownItem
                    key={i}
                    active={d.value === this.state.duration}
                    onClick={() => this.setState({duration: d.value})}>
                  {d.title}
                </DropdownItem>
             ))}
            </DropdownMenu>
          </InputGroupButtonDropdown>
        </InputGroup>
      </FormGroup>
    )
  }
}

class GeoLocation extends React.Component {
  constructor (props) {
    super(props)
    this.state = {address: '', error: null}
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
    let latlng
    try {
      const loc = await this.geocode({'address': this.state.address})
      latlng = loc.geometry.location
    } catch (e) {
      this.setState({error: 'location not found'})
      this.props.onChange(null)
      return
    }
    this.update(latlng)
  }

  async on_ondrag (e) {
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
      this.setState({address: address})
    }
    this.update(e.latLng, address)
  }

  update (loc, address) {
    this.props.onChange({lat: loc.lat(), lng: loc.lng(), name: address || this.state.address})
    this.setState({error: null})
  }

  on_key_press (e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      this.search()
    }
  }

  render () {
    const field = this.props.field
    // NOTE: this is hardcoded as central london for now
    const loc = this.props.value || {lat: 51.507382, lng: -0.127654, name: '', zoom: 12}
    return (
      <FormGroup>
        <Label field={field}/>
        <InputGroup>
          <BsInput type="text"
                   invalid={!!this.state.error}
                   disabled={this.props.disabled}
                   required={field.required}
                   placeholder={field.placeholder}
                   value={this.state.address}
                   onKeyPress={this.on_key_press.bind(this)}
                   onChange={e => this.setState({address: e.target.value})}/>
          <InputGroupAddon addonType="append">
            <Button onClick={this.search}>Search</Button>
          </InputGroupAddon>
        </InputGroup>
        <Map geolocation={loc} on_drag={this.on_ondrag.bind(this)}/>
        {this.state.error && <FormFeedback style={{display: 'block'}}>{this.state.error}</FormFeedback>}
        <HelpText field={field}/>
      </FormGroup>
    )
  }
}

const INPUT_LOOKUP = {
  'bool': Checkbox,
  'select': Select,
  'datetime': DatetimeInput,
  'integer': IntegerInput,
  'geolocation': GeoLocation,
}

const Input = props => {
  const InputComp = INPUT_LOOKUP[props.field.type] || GeneralInput
  props.field.title = props.field.title || as_title(props.field.name)
  return <InputComp {...props} onChange={props.set_value}/>
}

export default Input

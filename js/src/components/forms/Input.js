import React from 'react'
import {
  FormGroup,
  Label,
  Input as BsInput,
  CustomInput,
  FormText,
  FormFeedback,
  InputGroup,
  InputGroupAddon,
  Button
} from 'reactstrap'
import DatePicker from 'react-datepicker'
import moment from 'moment'
import {as_title} from '../../utils'
import Map from '../utils/Map'

window.moment = moment
const HelpText = ({field}) => (
  field.help_text ? <FormText>{field.help_text}</FormText> : <span/>
)

const GeneralInput = ({field, error, disabled, value, onChange, custom_type, step}) => (
  <FormGroup>
    <Label for={field.name}>{field.title}</Label>
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
             onChange={onChange}/>
    {error && <FormFeedback>{error}</FormFeedback>}
    <HelpText field={field}/>
  </FormGroup>
)

const Checkbox = ({field, disabled, value, onChange}) => (
  <FormGroup className="py-2" check>
    <Label check>
      <BsInput type="checkbox"
               label={field.title}
               disabled={disabled}
               name={field.name}
               required={field.required}
               checked={value || false}
               onChange={onChange}/>
      {field.title}
    </Label>
    <HelpText field={field}/>
  </FormGroup>
)

const Select = ({field, disabled, value, onChange}) => (
  <FormGroup>
    <Label for={field.name}>{field.title}</Label>
    <CustomInput type="select"
                 disabled={disabled}
                 name={field.name}
                 id={field.name}
                 required={field.required}
                 onChange={onChange}>
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

class DatetimeInput extends React.Component {
  constructor (props) {
    super(props)
    this.state = {all_day: false}
  }

  render () {
    const field = this.props.field
    return (
      <FormGroup>
        <Label for={field.name}>{field.title}</Label>
        <div className="d-flex justify-content-start">
          <DatePicker
            selected={this.props.value && moment(this.props.value.dt)}
            disabled={this.props.disabled}
            onChange={m => this.props.onChange(m && {dt: m.format(), ad: this.state.all_day})}
            showTimeSelect={!this.state.all_day}
            timeFormat="LT"
            required={field.required}
            dateFormat={this.state.all_day ? 'LL' : 'LLL'}
            placeholderText={this.state.all_day ? 'Click to select a date' : 'Click to select a date and time'}
            className="form-control"/>

          <label className="m-2">
            <input type="checkbox"
                   className="mx-2"
                   disabled={this.props.disabled}
                   checked={this.state.all_day}
                   onChange={e => this.setState({all_day: e.target.checked})}/>
            All Day
          </label>
        </div>
      </FormGroup>
    )
  }
}

class Location extends React.Component {
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
        <Label for={field.name}>{field.title}</Label>
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
        <Map location={loc} on_drag={this.on_ondrag.bind(this)}/>
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
  'location': Location,
}

const Input = props => {
  const on_change = event => {
    const value = (
      props.field.type === 'bool' ? event.target.checked :
      props.field.type === 'datetime' || props.field.type === 'location' ? event :
      event.target.value
    )
    props.set_value(value)
  }

  const InputComp = INPUT_LOOKUP[props.field.type] || GeneralInput
  props.field.title = props.field.title || as_title(props.field.name)
  return <InputComp {...props} onChange={on_change}/>
}

export default Input

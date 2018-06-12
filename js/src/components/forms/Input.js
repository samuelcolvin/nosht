import React from 'react'
import {FormGroup, Label, Input as BsInput, CustomInput, FormText, FormFeedback} from 'reactstrap'
import {as_title} from '../../utils'

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
          {choice.display_name}
        </option>
      ))}
    </CustomInput>
    <HelpText field={field}/>
  </FormGroup>
)

const IntegerInput = props => (
  <GeneralInput {...props} custom_type="number" step="1"/>
)

// TODO change
const DatetimeInput = ({field, disabled, value, onChange}) => {
  // could use https://stackoverflow.com/a/31162426/949890
  const re_match = value.match(/(.*?)T(.*)/)
  const render_values = {
    date: re_match ? re_match[1] : '',
    time: re_match ? re_match[2] : '',
  }

  const onChange_ = (event) => {
    render_values[event.target.getAttribute('type')] = event.target.value
    onChange({target: {value: render_values.date + 'T' + render_values.time}})
  }
  const required = field.required || render_values.date !== '' || render_values.time !== ''
  return (
    <label>
      {field.title}
      <div>
        <input type="date"
               className="date"
               name={field.name + '-date'}
               required={required}
               value={render_values.date}
               onChange={onChange_}/>
        <input type="time"
               className="time"
               step="300"
               name={field.name + '-time'}
               required={required}
               value={render_values.time}
               onChange={onChange_}/>
      </div>
    </label>
  )
}

const INPUT_LOOKUP = {
  'bool': Checkbox,
  'select': Select,
  'datetime': DatetimeInput,
  'integer': IntegerInput,
}

export default class Input extends React.Component {
  constructor (props) {
    super(props)
    this.on_change = this.on_change.bind(this)
  }

  on_change (event) {
    const value = this.props.field.type === 'bool' ? event.target.checked : event.target.value
    this.props.set_value(value)
  }

  render () {
    const InputComp = INPUT_LOOKUP[this.props.field.type] || GeneralInput
    this.props.field.title = this.props.field.title || as_title(this.props.field.name)
    return (
      <InputComp {...this.props} onChange={this.on_change}/>
    )
  }
}
